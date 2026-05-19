# GitLab CI Credentials

This document describes the credentials used by the GitLab CI pipelines and how they were provisioned.

## CI/CD Variables

These are configured in **Settings > CI/CD > Variables** on the GitLab project.

### `GITLAB_TOKEN`

- **Used by:** `mirror.yml` (PR mirroring workflow)
- **Purpose:** Pushes mirrored GitHub PR branches into the GitLab repo.
- **Type:** Personal or Project Access Token with `write_repository` scope.
- **How to create:** GitLab > Settings > Access Tokens > create a token with `write_repository`. Then add it as a CI/CD variable (Protected + Masked).

### `MODELS_CORP_*_API_KEY`

- **Used by:** `eval-gatekeeper.yml` (models.corp eval jobs)
- **Purpose:** Authenticates against the internal Red Hat model platform (`models.corp.redhat.com`) to run gatekeeper evals. Each variable follows the pattern `MODELS_CORP_<MODEL_NAME>_API_KEY` (e.g. `MODELS_CORP_GPT_OSS_20B_API_KEY`, `MODELS_CORP_GRANITE_4_0_H_SMALL_API_KEY`).
- **Type:** API key issued by models.corp.
- **How to create:** Check [models.corp user documentation](https://gitlab.cee.redhat.com/models-corp/user-documentation) for requesting an API key. Add it as a CI/CD variable (Protected + Masked). When adding a new models.corp eval job, create a corresponding variable following the naming convention.

## Secure Files

These are uploaded via **Settings > CI/CD > Secure Files** and downloaded at runtime by the `download-secure-files` job using `glab securefile download`.

### `gatekeeper-eval-service-account-credential.json`

- **Used by:** `eval-gatekeeper.yml` (all Vertex AI eval jobs, via `GOOGLE_APPLICATION_CREDENTIALS`)
- **Purpose:** Authenticates to the Google Cloud project `rhel-lightspeed-650189` to call Vertex AI model endpoints (e.g. `gpt-oss-120b-maas`, `gemini-3.1-pro-preview`).
- **Type:** Google Cloud Service Account key (JSON).
- **How it was created:**
  1. In the GCP console for project `rhel-lightspeed-650189`, a service account was created with the Vertex AI User role (or equivalent).
  2. A JSON key was exported for that service account.
  3. The JSON key file was uploaded to GitLab at **Settings > CI/CD > Secure Files**.
- **Rotation:** Generate a new JSON key in GCP, re-upload to Secure Files, and delete the old key.
