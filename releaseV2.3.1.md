# Span Extractor v2.3.1 Release Notes

## New Features

### Creation of Availability and Latency Watchers
Two new types of watchers can now be created:

1. **Latency Watcher**
   - Adds the condition `transaction.duration.us > threshold` to the head transaction
   - The threshold must be added in the input.csv file

2. **Availability Watcher**
   - Adds the condition `outcome.failure` to the head transaction

For each pattern, both watchers are generated.

## Improvements

### Updated Watcher Condition to Prevent Failure Execution on Empty Results
A comparison condition has been added to the watcher to ensure that the action will only execute if the EQL query result is non-empty. This prevents the execution failures we were experiencing previously.

