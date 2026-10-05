/**
 * Role checks shared by the screens that surface administrative affordances.
 *
 * The value comes from the locally stored `user_role` key, which
 * `authService.storeUser` writes from the server's user payload. It is a UI
 * affordance only: every administrative endpoint is authorised server-side, so
 * this must never be the thing that actually protects anything.
 */

/**
 * Role strings the backend uses for users who may administer the app.
 *
 * These must stay identical to the roles accepted by
 * `app.routes.auth_dependency.require_admin` in the backend. A role listed here
 * that the API does not accept hides the Admin tab from an administrator, and a
 * role missing here shows a tab whose every request fails with 403. The equality
 * is asserted by `backend/test_admin_tab_visibility.py`, so adding a role on one
 * side only fails the suite.
 */
const ADMIN_ROLES = new Set(["admin", "super_admin"]);

/**
 * Whether a stored role may see admin UI.
 *
 * `null` and `undefined` mean signed out, which is treated as non-admin: the
 * Admin tab and the Home admin button stay hidden until a role is known.
 */
export function isAdminRole(role: string | null | undefined): boolean {
  if (!role) {
    return false;
  }
  return ADMIN_ROLES.has(role.trim().toLowerCase());
}