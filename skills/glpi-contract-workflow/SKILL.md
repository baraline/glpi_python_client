---
name: glpi-contract-workflow
description: "Search, fetch, create, update, and delete GLPI contracts, their cost lines, and the contract-type dropdown, with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient, and the GetContract/PostContract/PatchContract/DeleteContract, GetContractCost/PostContractCost, and GetContractType/PostContractType models. Use for GLPI contract coverage, maintenance agreements, contract cost/budget lines, contract renewal type, or the contract-type dropdown."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials allowed to read or write contracts."
metadata:
  package: glpi-python-client
  version: "0.5.0"
---

# GLPI Contract Workflow
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

Contracts live under `/Management/Contract`, cost lines under the `/Management/Contract/{id}/Cost` sub-resource, and the type dropdown under `/Dropdowns/ContractType`. This skill owns the "what does this contract cover, for how much, and when does it renew" narrative. For *which assets* a contract covers, go through the asset side -- `list_computer_contracts` / `link_computer_contract` / `unlink_computer_contract` in `glpi-asset-workflow` -- there is no reverse lookup here that lists a contract's linked assets.

## Procedure

1. Create a `GlpiClient` from the `glpi-client-setup` skill.
2. Search contracts before creating duplicates: `search_contracts(rsql_filter, limit=..., start=..., sort=...)`. `sort` takes `"<field>:<direction>"`, e.g. `"date_begin:desc"`; omit it to leave server ordering in place. `iter_search_contracts(rsql_filter, batch_size=..., sort=...)` pages automatically.
3. Fetch one contract with `get_contract(contract_id)`.
4. Create with `create_contract(PostContract(...))`; returns the new `int` id. Update with `update_contract(contract_id, PatchContract(...))`; returns `None`. Delete with `delete_contract(contract_id, force=True|False|None)`.
5. For cost lines, use the `_contract_cost` family scoped by `contract_id`: `list_contract_costs(contract_id)`, `get_contract_cost(contract_id, cost_id)`, `create_contract_cost(contract_id, PostContractCost(...))`, `update_contract_cost(contract_id, cost_id, PatchContractCost(...))`, `delete_contract_cost(contract_id, cost_id, force=...)`. **Do not** try to write `costs` on `PostContract`/`PatchContract` -- see the gotcha below.
6. For the type dropdown, use `search_contract_types(rsql_filter, limit=..., start=...)`, `iter_search_contract_types(rsql_filter, batch_size=...)`, `get_contract_type(contract_type_id)`, `create_contract_type(PostContractType(...))`, `update_contract_type(contract_type_id, PatchContractType(...))`, `delete_contract_type(contract_type_id, force=...)`. **These two search helpers take no `sort` argument** -- unlike `search_contracts`/`search_computers`, passing `sort=` here is a `TypeError`, not a silent no-op.
7. Assign a contract's type and renewal behaviour through the parent contract, not through the type dropdown: `update_contract(contract_id, PatchContract(type=IdNameRef(id=type_id), renewal_type=GlpiContractRenewalType.TACIT))`.

## Examples

Create a contract, update it, and read it back:

```python
from glpi_python_client import PatchContract, PostContract
from datetime import date

contract_id = await client.create_contract(
    PostContract(
        name="Dell ProSupport 2026",
        number="CTR-2026-001",
        date_begin=date(2026, 1, 15),  # a date.date, not datetime -- see gotcha
    )
)
await client.update_contract(
    contract_id, PatchContract(comment="Renewed for another year")
)
contract = await client.get_contract(contract_id)
print(contract.id, contract.name, contract.date_begin)

matches = await client.search_contracts(
    "name==Dell ProSupport 2026", limit=5, sort="date_begin:desc"
)
for c in matches:
    print(c.id, c.name)
```

Add and update a cost line, then list and delete it:

```python
from datetime import datetime

from glpi_python_client import PatchContractCost, PostContractCost

cost_id = await client.create_contract_cost(
    contract_id,
    PostContractCost(
        name="Year 1",
        cost=4200.0,
        date_begin=datetime(
            2026, 1, 15, 0, 0
        ),  # a datetime here, unlike Contract.date_begin
    ),
)
await client.update_contract_cost(
    contract_id, cost_id, PatchContractCost(comment="Paid on invoice #88")
)
cost = await client.get_contract_cost(contract_id, cost_id)
print(cost.id, cost.name, cost.cost)

for line in await client.list_contract_costs(contract_id):
    print(line.id, line.name, line.cost)

await client.delete_contract_cost(contract_id, cost_id, force=True)
```

Create a contract type and assign it, with a renewal behaviour, to a contract:

```python
from glpi_python_client import (
    GlpiContractRenewalType,
    IdNameRef,
    PatchContract,
    PostContractType,
)

type_id = await client.create_contract_type(PostContractType(name="Maintenance"))
contract_type = await client.get_contract_type(type_id)
print(contract_type.id, contract_type.name)

await client.update_contract(
    contract_id,
    PatchContract(
        type=IdNameRef(id=type_id),
        renewal_type=GlpiContractRenewalType.TACIT,
    ),
)
```

Page through every contract type on the instance:

```python
async for batch in client.iter_search_contract_types("", batch_size=100):
    for t in batch:
        print(t.id, t.name)
```

## Gotchas

- **`Contract.date_begin` is a plain `datetime.date`, not `datetime.datetime`.** The GLPI contract declares it with `format: date` -- a contract has no time-of-day for its start -- and the server-clock conversion in `models/_base.py` only rewrites `datetime` instances, so a `date` never enters that conversion (which matters because converting a midnight, offset-naive `datetime` between timezones can roll it onto the previous or next calendar day). `ContractCost.date_begin` and `ContractCost.date_end` are the opposite: the contract declares those with `format: date-time`, so they are `datetime`. This asymmetry is real and comes from the GLPI contract itself, not an inconsistency to "fix" -- passing a `datetime` where `Contract.date_begin` expects a `date` (or vice versa for `ContractCost`) is the easy mistake here.
- **`costs` on `GetContract` is read-only.** It comes back populated with `IdRef` references to the contract's cost lines, but the field does not exist at all on `PostContract` or `PatchContract` -- there is nothing to assign there. Write cost lines through `create_contract_cost`, `update_contract_cost`, and `delete_contract_cost` instead.
- `GlpiContractRenewalType` (exported from `glpi_python_client`, an `IntEnum` subclass of `GlpiEnum`) has three members for `Contract.renewal_type`: `NONE = 0` (no renewal), `TACIT = 1` (automatic renewal), `EXPLICIT = 2` (manual renewal). Pass the member, not a bare integer.
- `search_contract_types` and `iter_search_contract_types` have **no `sort` parameter**, unlike `search_contracts`/`iter_search_contracts` and `search_computers`/`iter_search_computers`. Passing `sort=` to a contract-type search raises `TypeError` at the call site.
- `create_contract`, `create_contract_cost`, and `create_contract_type` return the new identifier as plain `int`. Every `update_*` and `delete_*` in this family returns `None`.
- `search_contracts`, `iter_search_contracts`, `search_contract_types`, and `iter_search_contract_types` raise `GlpiStatusError` on a 4xx rather than returning `[]` -- an empty list means the result set is genuinely empty. The v2 filter engine still silently drops an RSQL field it does not recognise and answers 200 with the whole table, so a non-empty result is not proof a filter was honoured.
- To find which assets a contract covers, do not search here -- there is no `items` field or reverse filter on `Contract`. Go through the owning asset's link helpers instead, e.g. `list_computer_contracts(computer_id)` in `glpi-asset-workflow`.
- Extra fields returned by the live server (on contracts, cost lines, or types) flow into `record.extra_payload` rather than raising.
