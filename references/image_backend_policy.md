# Image Backend Policy

Use this file only after the Background Gate has selected `ai-clean-plate` or a user explicitly asks for AI-assisted image editing.

FigEdit decides the reconstruction plan. The image backend only executes the approved preserve/remove/reconstruct brief.

## API Key Configuration

Scriptable backends read their keys from environment variables, and the
skill loads a dotenv file into them automatically: copy `env.example` at the
skill root to `.env`, fill in whatever keys you have, done. Real environment
variables take precedence over the file; `.env` is gitignored and must never
be committed or shared. `scripts/api_keys.py` is the loader; run it directly
to see which keys the file provides.

Practical note: Labnana GPT-Image-2 returns lossless PNG, which keys cleaner
than JPEG-returning backends (fewer compression artifacts on chroma edges) —
one more reason it leads the scriptable order.

## Backend Selection

Use the first reference-capable image editing path that is available and succeeds. **Before touching any scriptable backend, inventory your own tools**: if the agent environment exposes a built-in image generation/editing capability that accepts a reference image (Codex Image Gen, a bundled image tool, an image MCP), that is route 1 and must be tried first. `generate_clean_plate.py --precheck` only reports scriptable fallbacks — a positive precheck is not permission to skip this step.

1. **Built-in agent image tool (e.g. Codex `image_gen`)**. Use it first whenever the agent has any built-in image generation/editing tool, even when its parameter schema shows no reference-image or output-path options. Built-in tools receive the reference through the multimodal conversation context, not through parameters. Follow this invocation protocol:

   1. **Display the source image into the conversation first** (`view_image`
      in Codex, or the environment's equivalent way of showing an image to
      the model). This makes the source the visible edit target.
   2. **Then call the image tool.** The prompt must state explicitly that
      the image just displayed is the sole edit target, and phrase the
      preserve/remove/reconstruct brief relative to that image ("edit this
      image: remove …, keep … unchanged"), not as a fresh scene description.
   3. **Never substitute step 1 with a file path written inside the
      prompt.** A local path in prompt text does not transmit pixels; the
      tool only sees what is visible in the conversation.
   4. **Locate the output afterward.** Codex `image_gen` saves under
      `~/.codex/generated_images/<session>/`; take the newest file and copy
      it into the task workspace. A missing output-path parameter is normal,
      not a defect.

   Judge eligibility by **outcome, not parameter surface**: if the source
   can be displayed before the call and the produced bitmap can be located
   after it, the tool is eligible. "The built-in tool has no controllable
   reference/save parameters" is never a valid reason to fall back to
   scriptable backends — that exact rationalization has produced wrong
   fallbacks before; the reference goes in via the displayed image, not via
   a parameter. Fall back only after an actual invocation attempt fails
   (tool absent, call errors, or every candidate fails review), and record
   the failure before moving down the list.
2. **Labnana GPT-Image-2**. Outside Codex, or when Codex Image Gen is unavailable or fails, prefer Labnana with `provider=openai` and `model=gpt-image-2`. This is the preferred scriptable fallback because it supports reference-image generation/editing and arbitrary aspect ratios; do not force a standard aspect ratio when the source is non-standard.
3. **Labnana Gemini / Nano Banana**. If Labnana GPT-Image-2 is unavailable or fails, use Labnana with the Gemini/Nano Banana image model. Preserve the source aspect as closely as the provider allows.
4. **Official provider APIs**. If Labnana is unavailable, use direct OpenAI or Gemini image APIs only when the current environment has the required key, SDK/API capability, and reference-image editing support.

If no route is available, stop and report the blocker. Ask the user to configure an image backend/API key or approve a non-clean-plate route. Do not silently switch to local paint, blur, clone, fill, or inpaint.

Do not ask the user to confirm model, size, aspect ratio, or reference image when a configured default can complete the task. Ask only when no backend is configured, the user explicitly requests control, or the choice materially changes cost, rights, latency, or quality.

Do not choose Nano Banana before Codex Image Gen or Labnana GPT-Image-2 unless the user explicitly requests it or the higher-priority route failed and the failure was recorded.

## Capability Contract

A clean plate is an edit of the source image, not a fresh illustration. A backend is eligible only if it can:

- accept the original image as a reference or edit input
- preserve the source aspect ratio closely enough for later overlay alignment
- return a full-canvas bitmap suitable as the bottom visual layer
- follow a preserve/remove/reconstruct brief

Text-only image generation is not eligible for `ai-clean-plate` because it cannot preserve the specific source composition.

## Prompt and References

Before invocation, read `ai_clean_plate_prompting.md` and create a dynamic prompt from the actual source. The prompt should include:

- the source image as the primary reference
- preserve list
- remove list
- reconstruction instructions
- protected background inscriptions, if any
- same-as-source aspect ratio and full-bleed output requirement
- candidate rejection criteria

Optional references may include masks, removal overlays, or tight crops of objects that must retain identity. Do not provide unrelated style references unless the user asked for redesign.

## Optional Adapter Script

`scripts/generate_clean_plate.py` is an optional scriptable backend adapter. It is not the figure route selector and cannot invoke Codex Image Gen. It is used after the agent has selected `ai-clean-plate`, written the prompt brief, and determined that an interactive Codex Image Gen route is not being used.

Use it only after:

- the model has selected `ai-clean-plate`
- the generation brief has been written to a prompt file
- the environment has an eligible scriptable backend configured

The script checks backends in this order when `--backend auto` is used:

1. `labnana-gpt-image-2` with `LABNANA_API_KEY`
2. `labnana-nano-banana` with `LABNANA_API_KEY`
3. `openai-official` with `OPENAI_API_KEY` and local SDK/API support
4. `gemini-official` with `GEMINI_API_KEY` or `GOOGLE_API_KEY`
5. `configured-command` with `FIGEDIT_CLEAN_PLATE_CONFIG` or `--config`

Run `python scripts/generate_clean_plate.py --precheck` to see which scriptable routes are configured. A new installation with no backend should report `unavailable`; the agent should then use Codex Image Gen if present, or ask the user to configure a key/backend. The script may submit the request, save the returned bitmap, and write provenance. It must not create the clean plate through local blur, clone, fill, or OpenCV/PIL repair.

## Provenance

For the accepted plate, record:

- backend or tool used
- submitted prompt or prompt file
- source references actually supplied
- requested and recorded aspect ratio or output size
- output image path
- acceptance decision and candidate-review notes

The accepted output path must match the background plate asset used in the manifest.

## Failure Handling

Treat these as blockers unless the user explicitly approves a different route:

- no reference-capable backend is available
- every generated candidate fails review
- aspect ratio drift prevents overlay alignment
- the backend returns a redesigned image rather than a clean plate
- the candidate contains residual foreground text, hallucinated text, or missing major objects

Do not relabel a failed AI clean-plate route as conventional. Do not use the untouched source as the clean plate when it still contains the foreground that was supposed to be removed.
