# Inline step logging + live calibration readout — design

*2026-06-10 · approved by Artur (option 1, with option 3 noted as fallback)*

## Goal

Make logging actuals effortless (on the step card, no accordion/dropdown) and make
calibration visibly react after each log — both for real ADHD users and for the ~90s demo.

## Design (approved)

Replace the HTML results block with `@gr.render(inputs=rows_state)` dynamic rows:

- **Per step row**: number badge · step text · `AI: n min` chip · `For you: n min` chip ·
  inline `gr.Number` (minutes, scale-compact) · `Done` button.
- **On log**: `service.log_actual(step_id, minutes)` → recompute the view for the *same task*
  via the service's calibration → update `rows_state` → rows re-render; un-logged steps'
  "For you" chips shift immediately. Logged steps render with a ✓ and no inputs.
- **Readout line** (below the list, hidden until first log): plain-English per-category bias
  from the store's records, e.g. "Your *admin* estimates run ~1.8× long — adjusting for that."
- **Removed**: the "Log actual time" accordion, step dropdown, separate log button/status.
- **Unchanged**: schema/service/store/backend; export button; `build_ui(service)` signature
  (24 existing tests + smoke test unaffected).

State note: `rows_state` rows gain `logged: bool` and `actual_minutes: int | None`.
Recalibrated "For you" values for already-generated steps are recomputed UI-side by calling
the calibration on stored records — no new service API unless a thin helper is needed
(`service.recalibrate(rows)`, pure, unit-testable).

## Fallback (if `@gr.render` misbehaves on the Space)

Option 3 from brainstorm: keep plain-HTML cards with native `<input>` fields, bridged to a
hidden `gr.Textbox` via JS `js=`/`elem_id` wiring. Fragile across Gradio versions — use only
if dynamic render proves broken under Gradio 6.17.3 / ZeroGPU SSR.

## Verification

1. `pytest -q` green (24+).
2. Local `build_ui` constructs.
3. Deploy to Space → smoke test `/break_down` via gradio_client.
4. Browser screenshot: cards with inline inputs; log one actual → chips shift + readout shows.
