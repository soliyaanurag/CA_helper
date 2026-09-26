import { AppShell } from "@/components/AppShell";
import { PublicLayout } from "@/components/PublicLayout";
import { RequireRole } from "@/components/RequireRole";
import { ROLE_HOME } from "@/lib/session";
import { AdminDashboardPage } from "@/pages/admin/AdminDashboardPage";
import { AdminUsersPage } from "@/pages/admin/AdminUsersPage";
import { RegulatoryAdminPage } from "@/pages/admin/RegulatoryAdminPage";
import { AlertsPage } from "@/pages/business/AlertsPage";
import { AssistantPage } from "@/pages/business/AssistantPage";
import { BusinessDashboardPage } from "@/pages/business/BusinessDashboardPage";
import { CompliancePage } from "@/pages/business/CompliancePage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { MarketplacePage } from "@/pages/business/MarketplacePage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaDashboardPage } from "@/pages/ca/CaDashboardPage";
import { CaProfilePage } from "@/pages/ca/CaProfilePage";
import { CaWorkspacePage } from "@/pages/ca/CaWorkspacePage";
import { ChangePasswordPage } from "@/pages/ChangePasswordPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { HomePage } from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { SignupPage } from "@/pages/SignupPage";
import { VerifyEmailPage } from "@/pages/VerifyEmailPage";

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
    { label: "Notification settings", path: "/business/alerts" },
    { label: "AI assistant", path: "/business/assistant" },
  ],
  ca: [
    { label: "Dashboard", path: "/ca" },
    { label: "My profile", path: "/ca/profile" },
    { label: "My clients", path: "/ca/clients" },
  ],
  admin: [
    { label: "Dashboard", path: "/admin" },
    { label: "Users & CAs", path: "/admin/users" },
    { label: "Regulatory news", path: "/admin/regulatory" },
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
      { path: "verify-email", element: <VerifyEmailPage /> },
      { path: "forgot-password", element: <ForgotPasswordPage /> },
      { path: "reset-password", element: <ResetPasswordPage /> },
    ],
  },
  roleArea("business", [
    { index: true, element: <BusinessDashboardPage /> },
    { path: "onboarding", element: <OnboardingPage /> },
    { path: "compliance", element: <CompliancePage /> },
    { path: "documents", element: <DocumentsPage /> },
    { path: "marketplace", element: <MarketplacePage /> },
    { path: "alerts", element: <AlertsPage /> },
    { path: "assistant", element: <AssistantPage /> },
  ]),
  roleArea("ca", [
    { index: true, element: <CaDashboardPage /> },
    { path: "profile", element: <CaProfilePage /> },
    { path: "clients", element: <CaWorkspacePage /> },
  ]),
  roleArea("admin", [
    { index: true, element: <AdminDashboardPage /> },
    { path: "users", element: <AdminUsersPage /> },
    { path: "regulatory", element: <RegulatoryAdminPage /> },
  ]),
  { path: "*", element: <NotFoundPage /> },
];
