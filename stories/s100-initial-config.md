### Background

There is no initial config file that is read on startup, to minimally populate the application on startup.

### Feature Criteria

1. The application must boot up by reading this minimal config in initial.json. 

initial.json

1. There should also be a schema.json file (not provided), containing the valid data structures allowed in initial.json. The schema.json will be derived from the existing codebase and the demo-logins.csv (attached)

demo-logins.csv

### Repositories affected:

Frontend: Yes

Backend: Yes

### Scope

Do not perform any git push commands.

### Test Criteria

Create appropriate tests for this feature.

### Definition of Done

The test suite passes
