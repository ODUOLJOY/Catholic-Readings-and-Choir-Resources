// The API base is the backend service. The frontend is served separately, so
// this MUST point at the API host, NOT the frontend host. Pointing at the
// frontend host makes every API call (auth config, login, Google callback,
// choir resources, downloads) fail, which silently hides the Google button and
// breaks email login.
//
// The hostname must be the service name declared in `backend/render.yaml`
// (`catholic-readings-and-choir-resource-app`). It was previously
// `catholic-readings-and-choir-resources` (plural "resources"), which is not a
// hostname Render serves: every request to it answers `400 Invalid host
// header`, so auth, the choir library and downloads all failed in the shipped
// build while looking like ordinary network errors. Verify a host change with
// an OPTIONS/GET against `/api/choir/categories` before deploying it.
const PRODUCTION_API_URL = "https://catholic-readings-and-choir-resource-app.onrender.com";
// In a dev session (`expo start` / `expo run`) Metro inlines NODE_ENV="development",
// so local development points at the local backend per the README (`uvicorn
// app.main:app --reload` listens on http://127.0.0.1:8000). Shipping bundles
// (`expo export` / EAS) inline NODE_ENV="production" and keep the production
// origin here. `EXPO_PUBLIC_API_URL` always wins as an explicit override.
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production"
    ? PRODUCTION_API_URL
    : "http://127.0.0.1:8000");