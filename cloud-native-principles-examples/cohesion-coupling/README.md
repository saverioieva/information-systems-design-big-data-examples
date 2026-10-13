# Cohesion and Coupling Levels

## Goal

Use small Python examples to make the cohesion and coupling taxonomies from the
lecture concrete without introducing advanced microservice patterns.

This example follows the exact levels used in the course slides:

- **7 cohesion levels**: functional, sequential, communicational, procedural,
  temporal, logical, coincidental;
- **8 coupling levels**: no coupling, message, data, stamp, control, external,
  common/global, content/pathological.

The examples are intentionally simple. The goal is to compare **how code is
organized and how modules depend on each other**, not to build a realistic
business application.

## Run with Docker

Build the image once:

```bash
docker compose build
```

Show all cohesion examples:

```bash
docker compose run --rm demo python app.py cohesion
```

Show all coupling examples:

```bash
docker compose run --rm demo python app.py coupling
```

Show everything:

```bash
docker compose run --rm demo python app.py all
```

You can also run one level at a time. 

```bash
docker compose run --rm demo python app.py cohesion sequential
docker compose run --rm demo python app.py cohesion temporal
docker compose run --rm demo python app.py coupling data
docker compose run --rm demo python app.py coupling stamp
docker compose run --rm demo python app.py coupling content
```

## Cohesion: what to inspect

| Level | File | Main idea |
|---:|---|---|
| 1 | `cohesion/functional.py` | Every element contributes to one focused task. |
| 2 | `cohesion/sequential.py` | The output of one step becomes the input of the next. |
| 3 | `cohesion/communicational.py` | Operations work on the same data. |
| 4 | `cohesion/procedural.py` | Operations are grouped mainly by a required control flow. |
| 5 | `cohesion/temporal.py` | Different tasks are grouped because they execute at the same time. |
| 6 | `cohesion/logical.py` | Similar categories of operations share one generic entry point. |
| 7 | `cohesion/coincidental.py` | Unrelated tasks happen to be placed together. |

### A useful comparison

Compare these two files first:

```text
cohesion/functional.py
cohesion/coincidental.py
```

Then move through the intermediate levels. Ask: **why are these operations in
the same module?** The stronger the answer, the higher the cohesion.

## Coupling: what to inspect

| Level | File | Main idea |
|---:|---|---|
| 1 | `coupling/no_coupling.py` | Modules do not communicate or depend on each other. |
| 2 | `coupling/message_coupling.py` | Modules communicate through a narrow signal/message without sharing internal state. |
| 3 | `coupling/data_coupling.py` | Only the simple values required by the receiver are passed. |
| 4 | `coupling/stamp_coupling.py` | A whole structure is passed even though only part is required. |
| 5 | `coupling/control_coupling.py` | A flag or control parameter tells another module which behavior to execute. |
| 6 | `coupling/external_coupling.py` | Modules depend on the same externally imposed format or protocol. |
| 7 | `coupling/common_coupling.py` | Modules depend on shared global data. |
| 8 | `coupling/content_coupling.py` | One module directly accesses or changes another module's internal state. |

### A useful comparison

Run these three examples in order:

```bash
docker compose run --rm demo python app.py coupling data
docker compose run --rm demo python app.py coupling stamp
docker compose run --rm demo python app.py coupling content
```

The progression is deliberately visible in code:

```text
simple values -> whole structure -> another module's internals
```

This gives students a concrete way to see why coupling becomes harder to manage
as one module needs to know more about another module.

## Suggested lecture flow

For cohesion, start with the two extremes and then fill the middle:

```text
Functional -> Sequential -> Communicational -> Procedural
           -> Temporal -> Logical -> Coincidental
```

For coupling, follow the dependency scale in the slides:

```text
No -> Message -> Data -> Stamp -> Control
   -> External -> Common -> Content
```

Do not focus on the printed result alone. Open the corresponding `.py` file and
look at **what is shared, what is passed, and what each module needs to know**.

## Run without Docker

Python 3.10+ is enough:

```bash
python app.py cohesion
python app.py coupling
```

No third-party packages are required.

## Clean up

```bash
docker compose down --remove-orphans
```
