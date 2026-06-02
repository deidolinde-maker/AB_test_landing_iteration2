# Iteration 2 JSON Policy Update

For the current workflow, `applications` JSON keeps only successful submit scenarios.
This matches the README and the Jenkins pipeline for iteration 2.

Rule:

- append record only when `submit_success == true`;
- skip non-successful scenarios in `applications` payload;
- keep failed scenarios diagnostics in Allure and mini bug reports.

This policy is intentional for the handoff to the next iteration pipeline and keeps the
iteration 3 input clean.
