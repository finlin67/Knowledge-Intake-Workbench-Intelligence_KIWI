# KIWI Beginner Walkthroughs

## Scenario 1: First run

1. Double-click start_kiwi.bat from the parent KIWI folder.
2. Open the browser URL shown by the script (usually http://localhost:3000).
3. Confirm Home/Setup shows Backend: Online.
4. In Step 1, enter project info and click Save Project.

Expected result: Project is saved and Step 2 is ready.

## Scenario 2: Process your first batch

1. In Home/Setup Step 2, set import base path and batch folder name.
2. Click Scan Batch.
3. In Step 3 - Run Batch, click Run Batch.
4. Wait for completion.

Expected result: Files are processed and exported.

## Scenario 3: Continue with next batch

1. Click Start Next Batch.
2. Enter the next batch folder (for example batch_002).
3. Click Scan Batch.
4. Click Run Batch.

Expected result: New batch runs under the same project settings.

## Scenario 4: Resume later

1. Start KIWI again.
2. In Home/Setup, open Load Existing Project.
3. Enter your output folder path and load it.
4. Continue with Scan Batch and Run Batch.

Expected result: Existing project context is restored.

## Scenario 5: New project (not next batch)

1. In Home/Setup Step 1, click Edit Project Settings.
2. Change project name and export folder.
3. Click Save Project or Update Project.
4. Continue with Scan Batch and Run Batch.

Expected result: A new project context is used for future batches.
