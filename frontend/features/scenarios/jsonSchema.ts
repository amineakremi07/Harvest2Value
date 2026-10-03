// The subset of JSON Schema that pydantic emits for scenario change params (GET /api/v2/meta).

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export interface JsonSchema {
  type?: "object" | "string" | "number" | "integer" | "boolean" | "array" | "null";
  title?: string;
  description?: string;
  enum?: (string | number)[];
  const?: JsonValue;
  default?: JsonValue;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
  anyOf?: JsonSchema[];
  $ref?: string;
  $defs?: Record<string, JsonSchema>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Narrows the `params_schema` of /meta (typed `Record<string, unknown>`) to a JsonSchema. */
export function asJsonSchema(value: unknown): JsonSchema {
  return isRecord(value) ? (value as JsonSchema) : {};
}

/** Follows a local `#/$defs/Name` reference. */
export function resolve(schema: JsonSchema, root: JsonSchema): JsonSchema {
  if (!schema.$ref) return schema;
  const name = schema.$ref.replace(/^#\/\$defs\//, "");
  const target = root.$defs?.[name] ?? {};
  // Keys next to $ref (title, default) override the definition's.
  const { $ref: _ref, ...rest } = schema;
  void _ref;
  return { ...target, ...rest };
}

/** `anyOf: [X, {type: null}]` -> X marked nullable; other unions are returned as-is. */
export function unwrapNullable(schema: JsonSchema, root: JsonSchema): { schema: JsonSchema; nullable: boolean } {
  const resolved = resolve(schema, root);
  if (!resolved.anyOf) return { schema: resolved, nullable: false };
  const options = resolved.anyOf.filter((o) => o.type !== "null");
  const nullable = options.length < resolved.anyOf.length;
  if (options.length === 1) {
    return { schema: { ...resolve(options[0], root), title: resolved.title, default: resolved.default }, nullable };
  }
  return { schema: { ...resolved, anyOf: options }, nullable };
}

export function humanize(key: string, schema?: JsonSchema): string {
  return schema?.title ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** Initial value of a form for `schema`: defaults, first enum value, empty strings for numbers. */
export function initialValue(schema: JsonSchema, root: JsonSchema): JsonValue {
  const { schema: s, nullable } = unwrapNullable(schema, root);
  if (s.default !== undefined) return s.default;
  if (nullable) return null;
  if (s.const !== undefined) return s.const;
  if (s.enum && s.enum.length > 0) return s.enum[0];
  if (s.anyOf && s.anyOf.length > 0) return initialValue(s.anyOf[0], root);
  switch (s.type) {
    case "object": {
      const out: JsonObject = {};
      for (const [key, prop] of Object.entries(s.properties ?? {})) {
        // Required fields, plus optional ones with a default (e.g. cold_chain `entity`).
        const hasDefault = resolve(prop, root).default !== undefined && resolve(prop, root).default !== null;
        if ((s.required ?? []).includes(key) || hasDefault) out[key] = initialValue(prop, root);
      }
      return out;
    }
    case "boolean":
      return false;
    case "array":
      return [];
    case "number":
    case "integer":
      return "";
    default:
      return "";
  }
}

/**
 * Converts the form value to the API payload: numeric fields typed as strings become numbers,
 * empty optional fields are dropped. Returns the problems found (path -> message).
 */
export function toPayload(value: JsonValue, schema: JsonSchema, root: JsonSchema, path = ""): { value: JsonValue | undefined; errors: Record<string, string> } {
  const { schema: s, nullable } = unwrapNullable(schema, root);
  const errors: Record<string, string> = {};

  if (value === null || value === "") {
    if (nullable) return { value: undefined, errors };
    if (s.type === "string" && !s.minLength && !s.pattern) return { value: "", errors };
    errors[path] = "Valeur requise";
    return { value: undefined, errors };
  }

  if (s.anyOf) {
    // Union of a number and an enum (e.g. route value): keep whichever the value matches.
    const numeric = s.anyOf.map((o) => resolve(o, root)).find((o) => o.type === "number" || o.type === "integer");
    if (typeof value === "string" && numeric && value.trim() !== "" && !Number.isNaN(Number(value.replace(",", ".")))) {
      return toPayload(value, numeric, root, path);
    }
    return { value, errors };
  }

  switch (s.type) {
    case "number":
    case "integer": {
      const n = typeof value === "number" ? value : Number(String(value).replace(",", "."));
      if (!Number.isFinite(n)) errors[path] = "Nombre attendu";
      else if (s.type === "integer" && !Number.isInteger(n)) errors[path] = "Entier attendu";
      else if (s.minimum !== undefined && n < s.minimum) errors[path] = `Minimum ${s.minimum}`;
      else if (s.maximum !== undefined && n > s.maximum) errors[path] = `Maximum ${s.maximum}`;
      return { value: n, errors };
    }
    case "object": {
      const out: JsonObject = {};
      const obj = isRecord(value) ? (value as JsonObject) : {};
      for (const [key, prop] of Object.entries(s.properties ?? {})) {
        const required = (s.required ?? []).includes(key);
        const missing = !(key in obj) || obj[key] === "" || obj[key] === null;
        if (missing && !required) continue;
        if (!(key in obj)) {
          errors[path ? `${path}.${key}` : key] = "Valeur requise";
          continue;
        }
        const sub = toPayload(obj[key], prop, root, path ? `${path}.${key}` : key);
        Object.assign(errors, sub.errors);
        if (sub.value !== undefined) out[key] = sub.value;
      }
      return { value: out, errors };
    }
    case "array": {
      const items = Array.isArray(value) ? value : [];
      const out: JsonValue[] = [];
      items.forEach((item, i) => {
        const sub = toPayload(item, s.items ?? {}, root, `${path}[${i}]`);
        Object.assign(errors, sub.errors);
        if (sub.value !== undefined) out.push(sub.value);
      });
      return { value: out, errors };
    }
    default:
      return { value, errors };
  }
}
