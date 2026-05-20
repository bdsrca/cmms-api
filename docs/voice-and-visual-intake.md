# Voice and Visual Intake

Future CMMS/EAM intake should not require every user to type a perfect form.

Customers, technicians, and dispatchers often have different input habits. The system should accept those inputs while keeping one validation pipeline.

## Voice intake

Voice intake is best treated as transcript intake.

A safe flow:

1. User speaks.
2. Speech becomes transcript.
3. User can edit transcript.
4. API receives text.
5. Intake extraction runs.
6. Contract and environment validation run.
7. User reviews the draft.

The transcript is easier to audit and edit than raw audio. The public demo does not store audio.

## Screenshot or photo intake

Visual intake can help when a user has:

- a fault screen;
- a BMS alarm screenshot;
- a damaged equipment photo;
- a helpdesk ticket screenshot;
- a hand-written note;
- an equipment label.

A safe flow:

1. File upload passes size and type checks.
2. Vision or OCR extracts text and visible clues.
3. Intake agent creates a draft.
4. Asset and location checks run.
5. Policy checks run.
6. Review package returns evidence and warnings.

## Important boundary

Visual input should generate a draft, not a live work order. A screenshot can be unclear, cropped, or outdated. Human review remains necessary before write-back.
