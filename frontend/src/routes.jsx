import { useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { errorMessage } from "@/api";
import { useAuth } from "@/auth";
import { AssistantPage, AssistantWidget } from "@/components/assistant";
import { FormCard, NotificationBell } from "@/components/shared";
import { Button } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import {
  AdminAuditLogPage,
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
  RegulatoryAdminPage,
} from "@/pages/admin/AdminPages";
import { AlertsPage } from "@/pages/business/AlertsPage";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { MyEngagementsPage, ProBonoPage } from "@/pages/business/EngagementsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import {
  CaDetailPage,
  MarketplacePage,
  RequestCaPage,
  TypicalFeesPage,
} from "@/pages/business/FindCaPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaAlertsPage } from "@/pages/ca/CaAlertsPage";
import { CaBatchesPage, CaClientPage, CaWorkspacePage } from "@/pages/ca/ClientsPage";
import { CaDashboardPage } from "@/pages/ca/DashboardPage";
import { CaEngagementsPage, CaProBonoPage } from "@/pages/ca/EngagementsPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";

// --- routes ------------------------------------------------------------------------------------

/**
 * Every page of the app. To add a page: create it in pages/<role>/, add its
 * route below and, if it belongs in the sidebar, a link in NAV.
 */

/** Sidebar links for each role, in display order. */
export const NAV = {
  business: [
    { label: "Dashboard", path: "/business" },
    { label: "Business profile", path: "/business/onboarding" },
    { label: "Compliance calendar", path: "/business/compliance" },
    { label: "Document vault", path: "/business/documents" },
    { label: "Find a CA", path: "/business/marketplace" },
    { label: "Typical fees", path: "/business/fees" },
    { label: "My engagements", path: "/business/engagements" },
    { label: "Pro-bono help", path: "/business/pro-bono" },
    { label: "Notification settings", path: "/business/alerts" },
    { label: "AI assistant", path: "/business/assistant" },
  ],
  ca: [
    { label: "Dashboard", path: "/ca" },
    { label: "My profile", path: "/ca/profile" },
    { label: "Services & prices", path: "/ca/services" },
    { label: "My engagements", path: "/ca/engagements" },
    { label: "Pro-bono queue", path: "/ca/pro-bono" },
    { label: "My clients", path: "/ca/clients" },
    { label: "Deadline batches", path: "/ca/batches" },
    { label: "Notification settings", path: "/ca/alerts" },
  ],
  admin: [
    { label: "Dashboard", path: "/admin" },
    { label: "Users & CAs", path: "/admin/users" },
    { label: "Regulatory news", path: "/admin/regulatory" },
    { label: "Audit log", path: "/admin/audit" },
  ],
};

/**
 * One role's area: only that role may open it (RequireRole; the backend checks
 * again on every request), inside the sidebar layout. Child paths are relative
 * to the area, e.g. "documents" in the business area is /business/documents.
 * Every area also gets "change-password" (linked from the sidebar by AppShell).
 */
function roleArea(role, children) {
  return {
    path: ROLE_HOME[role],
    element: (
      <RequireRole role={role}>
        <AppShell role={role} nav={NAV[role]} />
      </RequireRole>
    ),
    children: [...children, { path: "change-password", element: <ChangePasswordPage /> }],
  };
}

export const appRoutes = [
  {
    path: "/",
    element: <PublicLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "login", element: <LoginPage /> },
      { path: "signup", element: <SignupPage /> },
      { path: "terms", element: <TermsPage /> },
      { path: "verify-email", element: <VerifyEmailPage /> },
      { path: "forgot-password", element: <ForgotPasswordPage /> },
      { path: "reset-password", element: <ResetPasswordPage /> },
    ],
  },
  roleArea("business", [
    { index: true, element: <BusinessDashboardPage /> },
    { path: "onboarding", element: <OnboardingPage /> },
    { path: "compliance", element: <CompliancePage /> },
    { path: "compliance/:itemId", element: <FilingPage /> },
    { path: "documents", element: <DocumentsPage /> },
    { path: "marketplace", element: <MarketplacePage /> },
    { path: "marketplace/:caId", element: <CaDetailPage /> },
    { path: "marketplace/:caId/request", element: <RequestCaPage /> },
    { path: "engagements", element: <MyEngagementsPage /> },
    { path: "pro-bono", element: <ProBonoPage /> },
    { path: "fees", element: <TypicalFeesPage /> },
    { path: "alerts", element: <AlertsPage /> },
    { path: "assistant", element: <AssistantPage /> },
  ]),
  roleArea("ca", [
    { index: true, element: <CaDashboardPage /> },
    { path: "profile", element: <CaProfilePage /> },
    { path: "services", element: <CaServicesPage /> },
    { path: "engagements", element: <CaEngagementsPage /> },
    { path: "pro-bono", element: <CaProBonoPage /> },
    { path: "clients", element: <CaWorkspacePage /> },
    { path: "clients/:businessId", element: <CaClientPage /> },
    { path: "batches", element: <CaBatchesPage /> },
    { path: "alerts", element: <CaAlertsPage /> },
  ]),
  roleArea("admin", [
    { index: true, element: <AdminDashboardPage /> },
    { path: "users", element: <AdminUsersPage /> },
    { path: "cas/:caId", element: <AdminCaDetailPage /> },
    { path: "regulatory", element: <RegulatoryAdminPage /> },
    { path: "audit", element: <AdminAuditLogPage /> },
  ]),
  { path: "*", element: <NotFoundPage /> },
];

// --- AppShell ----------------------------------------------------------------------------------

/**
 * Layout for the logged-in areas (/business, /ca, /admin): sidebar with the
 * notification bell, the role's links, user name, change password + logout, the
 * current page (<Outlet />) and, for business owners and CAs, the floating AI assistant.
 * `nav` is a list of { label, path } links (NAV in routes.jsx).
 *
 * The sidebar is exactly one screen tall and stays in place while the page scrolls
 * (sticky top-0 h-screen), so the name, "Change password" and "Log out" are always
 * visible at its bottom. If there are more links than fit, only the link list scrolls.
 */
export function AppShell({ role, nav }) {
  const { user, logout } = useAuth();
  const title = USER_ROLE_LABELS[role];
  const home = ROLE_HOME[role];

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r bg-muted/40 p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <Link to={home} className="text-lg font-semibold">
              CA Helper
            </Link>
            <p className="text-xs text-muted-foreground">{title}</p>
          </div>
          <NotificationBell />
        </div>
        <nav
          className="mt-6 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto"
          aria-label={`${title} navigation`}
        >
          {nav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === home} // the home link is active only on the home page
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm",
                  isActive ? "bg-primary text-primary-foreground" : "hover:bg-muted",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-2 border-t pt-4">
          <p className="truncate text-sm">{user?.full_name}</p>
          <Button asChild variant="ghost" size="sm" className="w-full">
            <Link to={`${home}/change-password`}>Change password</Link>
          </Button>
          <Button variant="outline" size="sm" className="w-full" onClick={logout}>
            Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-8">
        <Outlet />
      </main>
      {/* The floating AI assistant for business owners and CAs (not admins). */}
      {(role === "business" || role === "ca") && <AssistantWidget role={role} />}
    </div>
  );
}

// --- RequireRole -------------------------------------------------------------------------------

/**
 * Route guard for an area layout.
 * - Not logged in -> /login, and back here after logging in; except after the Log out
 *   button, when the next login goes to that role's home.
 * - Logged in with another role -> that role's own home.
 * - Signed up before consent was asked -> the consent step first (once).
 * The backend checks the role again on every request; this only keeps users
 * from landing on pages that would fail.
 */
export function RequireRole({ role, children }) {
  const { user, loggedOutOnPurpose, termsAccepted } = useAuth();
  const location = useLocation();

  if (!user) {
    const state = loggedOutOnPurpose ? undefined : { from: location.pathname };
    return <Navigate to="/login" replace state={state} />;
  }
  if (user.role !== role) {
    return <Navigate to={ROLE_HOME[user.role]} replace />;
  }
  if (termsAccepted === false) {
    return <AcceptTermsGate />; // asked once, for accounts from before consent
  }
  return children;
}

// --- PublicLayout ------------------------------------------------------------------------------

/** Layout for public pages: landing, login, signup, verify email, forgot/reset password. */
export function PublicLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b px-8 py-4">
        <Link to="/" className="text-lg font-semibold">
          CA Helper
        </Link>
      </header>
      <main className="mx-auto max-w-5xl p-8">
        <Outlet />
      </main>
    </div>
  );
}

// --- AcceptTermsGate ---------------------------------------------------------------------------

/**
 * Shown once, instead of the app, to a user who signed up before we asked for consent
 * (RequireRole renders it while `termsAccepted` is false).
 */
export function AcceptTermsGate() {
  const { acceptTerms, logout } = useAuth();
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function onAgree() {
    setError(null);
    setSaving(true);
    try {
      await acceptTerms();
    } catch (acceptError) {
      setError(errorMessage(acceptError));
      setSaving(false);
    }
  }

  return (
    <div className="p-8">
      <FormCard
        title="Our Terms and Privacy Policy"
        description="Before you continue, please read and accept how CA Helper stores and protects your data."
      >
        <Link
          to="/terms"
          target="_blank"
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Read the Terms and Privacy Policy
        </Link>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex gap-2">
          <Button onClick={onAgree} disabled={saving}>
            {saving ? "Saving..." : "I agree"}
          </Button>
          <Button variant="outline" onClick={logout}>
            Log out
          </Button>
        </div>
      </FormCard>
    </div>
  );
}
