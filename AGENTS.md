# AGENTS.md

## Working principles

### First-principles reasoning
Use first-principles reasoning.

Do not assume the user already knows exactly what they want or the best way to get it.
Start from the original problem, motivation, and goal.

If the motivation, target, constraints, or success criteria are unclear, stop and discuss with the user before making implementation decisions.

### Scope discipline
Do not introduce solutions outside the user's stated requirement.
Do not add fallback logic, compatibility layers, downgrade paths, or speculative extensions unless the user explicitly asks for them.

Prefer the shortest correct implementation path.
Do not over-design.

---

## TypeScript rules

When writing or modifying any TypeScript code:

1. Follow the project's TypeScript coding standards strictly.
2. Keep types explicit where business logic matters.
3. Avoid `any` unless there is no reasonable alternative.
4. Ensure the final code passes the full TypeScript build/type-check flow.
5. Do not introduce compatibility patches or partial migrations unless explicitly requested.

---

## Solution and refactor proposal rules

When proposing a modification plan or refactor plan, the plan must satisfy all of the following:

1. Do not propose compatibility-style or patch-style solutions.
2. Do not over-design.
3. Use the shortest correct implementation path.
4. Do not propose solutions beyond the user's stated requirement.
5. Do not add fallback, downgrade, or extra side-path logic that may shift business behavior.
6. Ensure the proposal is logically correct end-to-end.
7. Validate the proposal against the full request flow, not only a local code fragment.

Before presenting a plan, verify:

- the problem statement is clear
- the target behavior is clear
- the affected flow is fully identified
- the proposed change does not alter unrelated business logic

If any of the above is unclear, ask the user before proceeding.

---

## Implementation guardrails

When implementing changes:

1. Preserve business intent exactly.
2. Avoid broad refactors unless they are required by the user's request.
3. Keep changes minimal, direct, and traceable.
4. Prefer replacing incorrect logic with correct logic instead of layering fixes on top.
5. When debugging, identify the root cause first, then implement the minimal correct fix.
6. After changes, verify the full chain:
   - input
   - processing
   - state transitions
   - output
   - user-visible behavior

---

## Communication rules

When requirements are ambiguous:

- do not guess
- do not silently choose a business interpretation
- ask for clarification

When presenting a solution:

- explain the root cause first
- then give the minimal correct solution
- then explain the full affected flow
