import { Link, Outlet } from "react-router";

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
