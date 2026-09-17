---
name: glpi-asset-workflow
description: "Search, fetch, create, update, and delete GLPI computers, and read or write the contracts covering them, with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient, and the GetComputer/PostComputer/PatchComputer/DeleteComputer and GetContractItem/PostContractItem models. Use for GLPI asset inventory, computer records, asset serial numbers, asset locations, or finding which contracts cover a machine."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials allowed to read or write assets."
metadata:
  package: glpi-python-client
  version: "0.5.0"
---

# GLPI Asset Workflow
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

The asset mixin maps to `/Assets/Computer`. GLPI models roughly two dozen asset itemtypes (computers, monitors, printers, network equipment, and so on); **this client implements only `Computer`**. There is no `search_monitors`, `get_printer`, or any other asset-family method -- do not invent one, and do not assume a technique shown here (e.g. `sort`) extends to an asset type that has no methods at all. Treat `Computer` as the one supported asset type, not a stand-in for the rest of the family.

A computer's coverage is tracked separately as `Contract_Item` links under `/Assets/Computer/{id}/Contract`. This skill covers reading and writing those links from the computer side; for the contract record itself (dates, cost lines, renewal type, contract type) see `glpi-contract-workflow`.

## Procedure

1. Create a `GlpiClient` from the `glpi-client-setup` skill.
2. Search before creating duplicates: `search_computers(rsql_filter, limit=..., start=..., sort=...)`. `sort` takes `"<field>:<direction>"`, e.g. `"date_mod:desc"`; omit it to leave server ordering in place. `iter_search_computers(rsql_filter, batch_size=..., sort=...)` pages automatically and stops on the first short page -- prefer it over hand-rolling `start` increments.
3. Fetch one record with `get_computer(computer_id)`.
4. Create with `create_computer(PostComputer(...))`. Returns the new `int` id.
5. Update with `update_computer(computer_id, PatchComputer(...))`. Returns `None`.
6. Delete with `delete_computer(computer_id, force=True|False|None)`. `force=True` permanently deletes; omitted or `False`/`None` moves the record to the trash.
7. To find or record which contracts cover a computer, use the five link helpers below rather than searching `Contract` by computer -- there is no such filter, only the join.

## Examples

Search, create, and update a computer:

```python
from glpi_python_client import PatchComputer, PostComputer

computer_id = await client.create_computer(
    PostComputer(name="ws-1042", serial="PF3KL9QJ")
)
await client.update_computer(
    computer_id, PatchComputer(comment="Reimaged for the finance team")
)
computer = await client.get_computer(computer_id)
print(computer.id, computer.name, computer.serial)

matches = await client.search_computers("name==ws-1042", limit=5, sort="date_mod:desc")
for c in matches:
    print(c.id, c.name)
```

Page through every computer in an entity:

```python
async for batch in client.iter_search_computers("", batch_size=100):
    for c in batch:
        print(c.id, c.name, c.serial)
```

Link a computer to a contract, list its links, then unlink one:

```python
from glpi_python_client import IdNameRef, PostContractItem

link_id = await client.link_computer_contract(
    computer_id, PostContractItem(contract=IdNameRef(id=contract_id))
)

for link in await client.list_computer_contracts(computer_id):
    print(link.id, link.itemtype, link.items_id)

link = await client.get_computer_contract(computer_id, link_id)
print(link.contract)

await client.unlink_computer_contract(computer_id, link_id, force=True)
```

Update a link's `comment`-style fields without touching which asset it points at:

```python
from glpi_python_client import PatchContractItem

await client.update_computer_contract(
    computer_id, link_id, PatchContractItem(contract=IdNameRef(id=other_contract_id))
)
```

## Gotchas

- **`link_computer_contract` and `update_computer_contract` set `itemtype` and `items_id` themselves**, from the `computer_id` argument, overwriting whatever is set on the `PostContractItem`/`PatchContractItem` body passed in. `Contract_Item.itemtype` is a free string in the GLPI contract (`maxLength: 100`, not an enum) -- nothing server-side stops `"Computre"` from silently creating a link to a typo'd itemtype that matches no real asset. Pass only `contract` (and `comment`, if the resource ever adds one); do not bother setting `itemtype`/`items_id` on the body, they will be discarded.
- `create_computer` and `link_computer_contract` return the new identifier as plain `int`. `update_computer`, `update_computer_contract`, `delete_computer`, and `unlink_computer_contract` return `None`.
- `search_computers` and `iter_search_computers` raise `GlpiStatusError` on a 4xx rather than returning `[]` -- an empty list means the server said the result set is empty, not that the filter was rejected. The usual v2 caveat still applies on the *other* side: an RSQL field the server does not recognise is silently dropped and the call answers 200 with the whole unfiltered table, so a non-empty result is not proof the filter took effect.
- `list_computer_contracts` returns `GetContractItem` records, not `GetContract`. Each carries `contract` (an `IdNameRef` pointing at the actual contract), `itemtype`, and `items_id` -- to read the contract's own fields (dates, type, renewal), call `get_contract(link.contract.id)` from `glpi-contract-workflow`.
- Extra fields returned by the live server flow into `record.extra_payload` rather than raising.
- If the caller provides a name or serial rather than an id, search first (`search_computers('serial=="PF3KL9QJ"')`) and confirm the id before updating or deleting.
