import type { RouteObject } from "react-router";

import { RequireRole } from "@/core/auth/RequireRole";
import { USER_ROLE_LABELS } from "@/core/labels";
import { AppShell, type NavItem } from "@/core/layout/AppShell";
import { PublicLayout } from "@/core/layout/PublicLayout";
import { HomePage } from "@/core/pages/HomePage";
import { LoginPage } from "@/core/pages/LoginPage";
import { NotFoundPage } from "@/core/pages/NotFoundPage";
import { routes as adminRoutes } from "@/features/admin/routes";
import { routes as alertsRoutes } from "@/features/alerts/routes";
import { routes as assistantRoutes } from "@/features/assistant/routes";
import { routes as caWorkspaceRoutes } from "@/features/ca_workspace/routes";
import { routes as complianceRoutes } from "@/features/compliance/routes";
import { routes as documentsRoutes } from "@/features/documents/routes";
import { routes as marketplaceRoutes } from "@/features/marketplace/routes";
import { routes as onboardingRoutes } from "@/features/onboarding/routes";
import { routes as regulatoryRoutes } from "@/features/regulatory/routes";

/*
 * Every page of the app. Each logged-in area (/business, /ca, /admin) is only for
 * its role (RequireRole; the backend checks the role again on every request) and
 * shows its pages inside AppShell with the sidebar links listed below.
 */

const BUSINESS_NAV: NavItem[] = [
  { label: "Dashboard", path: "/business" },
  { label: "Business profile", path: "/business/onboarding" },
  { label: "Compliance calendar", path: "/business/compliance" },
  { label: "Document vault", path: "/business/documents" },
  { label: "Find a CA", path: "/business/marketplace" },
  { label: "Notification settings", path: "/business/alerts" },
  { label: "AI assistant", path: "/business/assistant" },
];

const CA_NAV: NavItem[] = [
  { label: "Dashboard", path: "/ca" },
  { label: "My clients", path: "/ca/clients" },
];

const ADMIN_NAV: NavItem[] = [
  { label: "Dashboard", path: "/admin" },
  { label: "Users & CAs", path: "/admin/users" },
  { label: "Regulatory news", path: "/admin/regulatory" },
];

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <PublicLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "login", element: <LoginPage /> },
    ],
  },
  {
    path: "/business",
    element: (
      <RequireRole role="business">
        <AppShell title={USER_ROLE_LABELS.business} home="/business" nav={BUSINESS_NAV} />
      </RequireRole>
    ),
    // Add your feature's routes here.
    children: [
      ...complianceRoutes,
      ...onboardingRoutes,
      ...documentsRoutes,
      ...marketplaceRoutes,
      ...alertsRoutes,
      ...assistantRoutes,
    ],
  },
  {
    path: "/ca",
    element: (
      <RequireRole role="ca">
        <AppShell title={USER_ROLE_LABELS.ca} home="/ca" nav={CA_NAV} />
      </RequireRole>
    ),
    // Add your feature's routes here.
    children: [...caWorkspaceRoutes],
  },
  {
    path: "/admin",
    element: (
      <RequireRole role="admin">
        <AppShell title={USER_ROLE_LABELS.admin} home="/admin" nav={ADMIN_NAV} />
      </RequireRole>
    ),
    // Add your feature's routes here.
    children: [...adminRoutes, ...regulatoryRoutes],
  },
  { path: "*", element: <NotFoundPage /> },
];
