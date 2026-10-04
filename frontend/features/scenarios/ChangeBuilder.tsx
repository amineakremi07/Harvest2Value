"use client";

import { useId, useMemo, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { Button, Field, inputClass } from "@/components/ui/primitives";
import type { ChangeInput, ChangeOpInfo, DatasetPayload } from "@/lib/api/types";
import { asJsonSchema, initialValue, toPayload, type JsonObject, type JsonValue } from "./jsonSchema";
import { SchemaForm } from "./SchemaForm";
import { opLabel, targetOptions } from "./targets";

function asObject(value: JsonValue): JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value : {};
}

/**
 * Builds one scenario change. The op list and each op's parameter form come from
 * GET /api/v2/meta (`change_ops[].params_schema`); targets come from the effective data.
 */
export function ChangeBuilder({
  ops,
  payload,
  onAdd,
  submitting = false,
}: {
  ops: ChangeOpInfo[];
  payload: DatasetPayload | undefined;
  onAdd: (change: ChangeInput) => Promise<boolean> | boolean;
  submitting?: boolean;
}) {
  const id = useId();
  const [op, setOp] = useState<string>(ops[0]?.op ?? "");
  const info = ops.find((o) => o.op === op);
  const schema = useMemo(() => asJsonSchema(info?.params_schema), [info]);
  const [params, setParams] = useState<JsonValue>(() => initialValue(schema, schema));
  const [target, setTarget] = useState<string>("");
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const options = info ? targetOptions(info.op, info.target, payload, asObject(params)) : [];
  const effectiveTarget = options.some((o) => o.value === target) ? target : (options[0]?.value ?? "");

  function changeOp(next: string) {
    const nextInfo = ops.find((o) => o.op === next);
    const nextSchema = asJsonSchema(nextInfo?.params_schema);
    setOp(next);
    setParams(initialValue(nextSchema, nextSchema));
    setTarget("");
    setErrors({});
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!info) return;
    const converted = toPayload(params, schema, schema);
    const problems = { ...converted.errors };
    if (info.target !== "none" && !effectiveTarget) problems.target = "Choisissez une cible";
    setErrors(problems);
    if (Object.keys(problems).length > 0) return;
    const added = await onAdd({
      op: info.op,
      target: info.target === "none" ? null : effectiveTarget,
      params: asObject(converted.value ?? {}),
      note: note.trim() || null,
    });
    if (added) {
      setParams(initialValue(schema, schema));
      setNote("");
    }
  }

  if (ops.length === 0) return <p className="text-sm text-slate-400">Aucune opération disponible.</p>;

  return (
    <form onSubmit={submit} className="space-y-4" aria-label="Nouvelle modification">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Opération" htmlFor={`${id}-op`} hint={info?.description}>
          <select id={`${id}-op`} className={inputClass} value={op} onChange={(e) => changeOp(e.target.value)}>
            {ops.map((o) => (
              <option key={o.op} value={o.op}>
                {opLabel(o.op)}
              </option>
            ))}
          </select>
        </Field>
        {info && info.target !== "none" && (
          <Field label="Cible" htmlFor={`${id}-target`}>
            <select id={`${id}-target`} className={inputClass} value={effectiveTarget} onChange={(e) => setTarget(e.target.value)}>
              {options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            {errors.target && <p className="text-xs text-rose-300">{errors.target}</p>}
          </Field>
        )}
      </div>
      <SchemaForm key={op} schema={schema} value={params} onChange={setParams} errors={errors} />
      <Field label="Note (optionnelle)" htmlFor={`${id}-note`}>
        <input id={`${id}-note`} className={inputClass} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <Button type="submit" variant="primary" busy={submitting}>
        <Plus className="h-4 w-4" aria-hidden="true" />
        Ajouter la modification
      </Button>
    </form>
  );
}
