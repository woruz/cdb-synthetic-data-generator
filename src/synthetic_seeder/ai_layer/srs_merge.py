"""Merge multiple SRS structured outputs (from chunked long documents)."""

from __future__ import annotations

from synthetic_seeder.ai_layer.srs_schemas import (
    ConstraintDef,
    EntityField,
    RelationshipDef,
    RoleDef,
    SRSEntity,
    SRSStructuredOutput,
    StateMachineDef,
    WorkflowDef,
)


def _entity_key(e: SRSEntity) -> str:
    return e.name.strip().lower()


def _relationship_key(r: RelationshipDef) -> tuple:
    return (
        r.from_entity.strip().lower(),
        r.to_entity.strip().lower(),
        (r.from_field or "").strip().lower(),
        (r.to_field or "").strip().lower(),
    )


def _state_machine_key(s: StateMachineDef) -> str:
    return s.entity_or_field.strip().lower()


def _workflow_key(w: WorkflowDef) -> str:
    return w.name.strip().lower()


def _constraint_key(c: ConstraintDef) -> tuple:
    return (c.entity.strip().lower(), (c.field or "").strip().lower(), c.constraint_type.strip().lower())


def _role_key(r: RoleDef) -> str:
    return r.name.strip().lower()


def _merge_entity_fields(existing: list[EntityField], new: list[EntityField]) -> list[EntityField]:
    by_name = {f.name.strip().lower(): f for f in existing}
    for f in new:
        k = f.name.strip().lower()
        if k not in by_name:
            by_name[k] = f
        else:
            old = by_name[k]
            if f.enum_values and not old.enum_values:
                by_name[k] = old.model_copy(update={"enum_values": f.enum_values})
            if f.max_length is not None and old.max_length is None:
                by_name[k] = old.model_copy(update={"max_length": f.max_length})
            if f.description and not old.description:
                by_name[k] = old.model_copy(update={"description": f.description})
    return list(by_name.values())


def merge_srs_outputs(outputs: list[SRSStructuredOutput]) -> SRSStructuredOutput:
    """
    Merge multiple SRS extractions (e.g. from chunked PDF pages) into one.
    Entities are merged by name; relationships, state_machines, etc. are deduplicated.
    """
    if not outputs:
        return SRSStructuredOutput()
    if len(outputs) == 1:
        return outputs[0]

    entities_by_name: dict[str, SRSEntity] = {}
    for out in outputs:
        for e in out.entities:
            k = _entity_key(e)
            if k not in entities_by_name:
                entities_by_name[k] = e
            else:
                existing = entities_by_name[k]
                merged_fields = _merge_entity_fields(existing.fields, e.fields)
                merged_state = {**existing.state_fields, **e.state_fields}
                desc = existing.description or e.description
                entities_by_name[k] = SRSEntity(
                    name=existing.name,
                    fields=merged_fields,
                    description=desc,
                    state_fields=merged_state,
                )

    seen_rel = set()
    relationships = []
    for out in outputs:
        for r in out.relationships:
            key = _relationship_key(r)
            if key not in seen_rel:
                seen_rel.add(key)
                relationships.append(r)

    sm_by_key: dict[str, StateMachineDef] = {}
    for out in outputs:
        for s in out.state_machines:
            k = _state_machine_key(s)
            if k not in sm_by_key:
                sm_by_key[k] = s
            else:
                existing = sm_by_key[k]
                combined = list(dict.fromkeys(existing.states + s.states))
                sm_by_key[k] = StateMachineDef(
                    entity_or_field=existing.entity_or_field,
                    states=combined,
                    description=existing.description or s.description,
                )
    state_machines = list(sm_by_key.values())

    seen_wf = set()
    workflows = []
    for out in outputs:
        for w in out.workflows:
            k = _workflow_key(w)
            if k not in seen_wf:
                seen_wf.add(k)
                workflows.append(w)

    seen_const = set()
    constraints = []
    for out in outputs:
        for c in out.constraints:
            key = _constraint_key(c)
            if key not in seen_const:
                seen_const.add(key)
                constraints.append(c)

    seen_roles = set()
    roles = []
    for out in outputs:
        for r in out.roles:
            k = _role_key(r)
            if k not in seen_roles:
                seen_roles.add(k)
                roles.append(r)

    enums_merged: dict[str, list[str]] = {}
    for out in outputs:
        for name, values in out.enums.items():
            key = name.strip().lower()
            if key not in enums_merged:
                enums_merged[key] = list(values) if values else []
            else:
                enums_merged[key] = list(dict.fromkeys(enums_merged[key] + (values or [])))

    return SRSStructuredOutput(
        entities=list(entities_by_name.values()),
        relationships=relationships,
        state_machines=state_machines,
        workflows=workflows,
        constraints=constraints,
        roles=roles,
        enums=enums_merged,
    )
