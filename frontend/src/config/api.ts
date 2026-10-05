// The API base is the backend service. The frontend is served separately, so
// this MUST point at the API host (https://catholic-readings-and-choir-
// resources.onrender.com), NOT the frontend host. Pointing at the frontend
// host makes every API call (auth config, login, Google callback, choir files)
// fail, which silently hides the Google button and breaks email login.
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  "https://catholic-readings-and-choir-resources.onrender.com";