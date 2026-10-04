"use client";

import { useId, type ReactNode } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button, inputClass } from "@/components/ui/primitives";
import { humanize, initialValue, resolve, unwrapNullable, type JsonObject, type JsonSchema, type JsonValue } from "./jsonSchema";

/** Labels for the pydantic field and enum names used by the change params. */
const LABELS: Record<string, string> = {
  mode: "Mode",
  value: "Valeur",
  field: "Champ",
  shift_days: "Décalage (jours)",
  required: "Requise",
  entity: "Entité",
  absolute: "Valeur absolue",
  relative_pct: "Variation en %",
  delta: "Variation absolue",
  max_demand_kg: "Demande max (kg)",
  max_per_day_kg: "Max par jour (kg)",
  min_contract_kg: "Minimum contractuel (kg)",
  cost_per_km: "Coût par km",
  fixed_cost_per_trip: "Coût fixe par trajet",
  ambient: "Ambiante",
  cold: "Froid",
  distance_km: "Distance (km)",
  road_condition: "État de la route",
  toll_per_trip: "Péage par trajet",
  buyer: "Acheteur",
  crop: "Culture",
  good: "Bonne",
  fair: "Moyenne",
  poor: "Mauvaise",
};

function label(key: string, schema?: JsonSchema): string {
  return LABELS[key] ?? humanize(key, schema);
}

interface FieldProps {
  name: string;
  schema: JsonSchema;
  root: JsonSchema;
  value: JsonValue;
  onChange: (value: JsonValue) => void;
  path: string;
  required: boolean;
  errors: Record<string, string>;
}

function SchemaField({ name, schema, root, value, onChange, path, required, errors }: FieldProps) {
  const id = useId();
  const { schema: s, nullable } = unwrapNullable(schema, root);
  const title = `${label(name, s)}${required || !nullable ? "" : " (optionnel)"}`;
  const error = errors[path];

  const wrap = (control: ReactNode) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        {title}
      </label>
      {control}
      {s.description && <p className="text-xs text-slate-500">{s.description}</p>}
      {error && <p className="text-xs text-rose-300">{error}</p>}
    </div>
  );

  if (s.type === "object" && s.properties) {
    return (
      <fieldset className="rounded-lg border border-card-border p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-slate-400">{label(name, s)}</legend>
        <ObjectFields schema={s} root={root} value={value} onChange={onChange} path={path} errors={errors} />
      </fieldset>
    );
  }

  if (s.enum) {
    return wrap(
      <select id={id} className={inputClass} value={value == null ? "" : String(value)} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}>
        {nullable && <option value="">—</option>}
        {s.enum.map((option) => (
          <option key={String(option)} value={String(option)}>
            {LABELS[String(option)] ?? String(option)}
          </option>
        ))}
      </select>,
    );
  }

  if (s.type === "boolean") {
    return (
      <label className="flex items-center gap-2 text-sm text-slate-200">
        <input id={id} type="checkbox" checked={value === true} onChange={(e) => onChange(e.target.checked)} />
        {title}
      </label>
    );
  }

  if (s.anyOf) {
    // Union such as "road condition or number": free input with the enum values suggested.
    const suggestions = s.anyOf.flatMap((o) => resolve(o, root).enum ?? []);
    const listId = `${id}-list`;
    return wrap(
      <>
        <input id={id} list={listId} className={inputClass} value={value == null ? "" : String(value)} onChange={(e) => onChange(e.target.value)} />
        <datalist id={listId}>
          {suggestions.map((o) => (
            <option key={String(o)} value={String(o)} />
          ))}
        </datalist>
      </>,
    );
  }

  if (s.type === "array") {
    const items = Array.isArray(value) ? value : [];
    const itemSchema = resolve(s.items ?? {}, root);
    if (itemSchema.type === "object") {
      return (
        <fieldset className="rounded-lg border border-card-border p-3">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</legend>
          <div className="space-y-3">
            {items.map((item, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="flex-1">
                  <ObjectFields
                    schema={itemSchema}
                    root={root}
                    value={item}
                    onChange={(v) => onChange(items.map((old, j) => (j === i ? v : old)))}
                    path={`${path}[${i}]`}
                    errors={errors}
                  />
                </div>
                <Button variant="ghost" aria-label="Supprimer la ligne" onClick={() => onChange(items.filter((_, j) => j !== i))}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            ))}
            <Button onClick={() => onChange([...items, initialValue(itemSchema, root)])}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Ajouter
            </Button>
          </div>
        </fieldset>
      );
    }
    // Array of scalars (ids): comma-separated.
    return wrap(
      <input
        id={id}
        className={inputClass}
        placeholder="valeur1, valeur2"
        value={items.map(String).join(", ")}
        onChange={(e) =>
          onChange(
            e.target.value
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean),
          )
        }
      />,
    );
  }

  const numeric = s.type === "number" || s.type === "integer";
  return wrap(
    <input
      id={id}
      className={inputClass}
      inputMode={numeric ? "decimal" : undefined}
      maxLength={s.maxLength}
      placeholder={numeric && s.minimum !== undefined && s.maximum !== undefined && Math.abs(s.maximum) < 1e6 ? `${s.minimum} … ${s.maximum}` : undefined}
      value={value == null ? "" : String(value)}
      onChange={(e) => onChange(e.target.value)}
    />,
  );
}

function ObjectFields({
  schema,
  root,
  value,
  onChange,
  path,
  errors,
}: {
  schema: JsonSchema;
  root: JsonSchema;
  value: JsonValue;
  onChange: (value: JsonValue) => void;
  path: string;
  errors: Record<string, string>;
}) {
  const obj: JsonObject = typeof value === "object" && value !== null && !Array.isArray(value) ? value : {};
  const entries = Object.entries(schema.properties ?? {});
  if (entries.length === 0) return <p className="text-sm text-slate-500">Aucun paramètre.</p>;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {entries.map(([key, prop]) => (
        <SchemaField
          key={key}
          name={key}
          schema={prop}
          root={root}
          value={key in obj ? obj[key] : initialValue(prop, root)}
          onChange={(v) => onChange({ ...obj, [key]: v })}
          path={path ? `${path}.${key}` : key}
          required={(schema.required ?? []).includes(key)}
          errors={errors}
        />
      ))}
    </div>
  );
}

/** Form generated from a change op's `params_schema` (GET /api/v2/meta). */
export function SchemaForm({
  schema,
  value,
  onChange,
  errors = {},
}: {
  schema: JsonSchema;
  value: JsonValue;
  onChange: (value: JsonValue) => void;
  errors?: Record<string, string>;
}) {
  return <ObjectFields schema={schema} root={schema} value={value} onChange={onChange} path="" errors={errors} />;
}
