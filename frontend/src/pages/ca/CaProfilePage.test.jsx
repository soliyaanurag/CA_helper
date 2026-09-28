import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const URL = "/api/v1/marketplace/ca-profile";
const NOT_FOUND = [
  404,
  { error: { code: "CA_PROFILE_NOT_FOUND", message: "You have not completed your profile yet." } },
];

const SAVED = {
  id: "0b5f0b8e-4a8e-4bb1-9f0e-1c2d3e4f5a6b",
  membership_no: "123456",
  cop_number: "COP-7788",
  city: "Pune",
  languages: ["english", "marathi"],
  specializations: ["itr", "gstr_3b"],
  capacity: 20,
  years_experience: 5,
  about: "",
  verification_status: "pending",
  updated_at: "2026-09-26T10:00:00Z",
};

async function fillForm() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("ICAI membership number"), "123456");
  await user.type(screen.getByLabelText("Certificate of Practice number"), "COP-7788");
  await user.type(screen.getByLabelText("City"), "Pune");
  await user.type(screen.getByLabelText("Years of experience"), "5");
  await user.type(screen.getByLabelText("Capacity (clients at a time)"), "20");
  await user.click(screen.getByLabelText("Income tax return (ITR)"));
  await user.click(screen.getByLabelText("GSTR-3B"));
  await user.click(screen.getByLabelText("English"));
  await user.click(screen.getByLabelText("Marathi"));
  return user;
}

describe("CA profile page", () => {
  it("is linked from the CA sidebar", async () => {
    loginAs("ca");
    fakeApi({ [`GET ${URL}`]: NOT_FOUND });
    renderApp("/ca");

    expect(await screen.findByRole("link", { name: "My profile" })).toHaveAttribute(
      "href",
      "/ca/profile",
    );
  });

  it("reminds a CA without a profile on the dashboard", async () => {
    loginAs("ca");
    fakeApi({ [`GET ${URL}`]: NOT_FOUND });
    renderApp("/ca");

    expect(await screen.findByText("Complete your profile")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Complete profile" })).toHaveAttribute(
      "href",
      "/ca/profile",
    );
  });

  it("shows no reminder once the CA is verified", async () => {
    loginAs("ca");
    fakeApi({
      "GET /api/v1/ca-workspace/dashboard": [200, { message: "Welcome, Test ca" }],
      [`GET ${URL}`]: [200, { ...SAVED, verification_status: "verified" }],
    });
    renderApp("/ca");

    expect(await screen.findByRole("heading", { name: "Welcome, Test ca" })).toBeInTheDocument();
    for (const name of ["Complete profile", "View profile", "Edit profile"]) {
      expect(screen.queryByRole("link", { name })).not.toBeInTheDocument();
    }
  });

  it("saves a new profile and shows it is pending verification", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({ [`GET ${URL}`]: NOT_FOUND, [`PUT ${URL}`]: [200, SAVED] });
    renderApp("/ca/profile");

    await screen.findByText(/Complete your profile/);
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Profile saved.");
    expect(screen.getByText("Pending verification")).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "PUT");
    expect(JSON.parse(init.body)).toEqual({
      membership_no: "123456",
      cop_number: "COP-7788",
      city: "Pune",
      languages: ["english", "marathi"],
      specializations: ["itr", "gstr_3b"],
      capacity: 20,
      years_experience: 5,
      pro_bono_slots_per_month: 0,
      about: "",
    });
  });

  it("checks the fields before sending anything", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({ [`GET ${URL}`]: NOT_FOUND });
    renderApp("/ca/profile");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Save profile" }));

    expect(
      await screen.findByText("Enter your 6-digit ICAI membership number."),
    ).toBeInTheDocument();
    expect(screen.getByText("Choose at least one specialization.")).toBeInTheDocument();
    expect(screen.getByText("Choose at least one language.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
  });

  it("fills the form with the saved profile", async () => {
    loginAs("ca");
    fakeApi({ [`GET ${URL}`]: [200, { ...SAVED, verification_status: "rejected" }] });
    renderApp("/ca/profile");

    expect(await screen.findByLabelText("ICAI membership number")).toHaveValue("123456");
    expect(screen.getByLabelText("GSTR-3B")).toBeChecked();
    expect(screen.getByLabelText("GSTR-1")).not.toBeChecked();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("shows a membership number that another CA already uses", async () => {
    loginAs("ca");
    fakeApi({
      [`GET ${URL}`]: NOT_FOUND,
      [`PUT ${URL}`]: [
        409,
        {
          error: {
            code: "DUPLICATE_MEMBERSHIP_NO",
            message: "Another CA has already registered this membership number.",
          },
        },
      ],
    });
    renderApp("/ca/profile");

    await screen.findByText(/Complete your profile/);
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    const field = screen.getByLabelText("ICAI membership number");
    await waitFor(() =>
      expect(field).toHaveAccessibleDescription(
        "Another CA has already registered this membership number.",
      ),
    );
    expect(field).toHaveFocus();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("labels specializations and languages in words", async () => {
    loginAs("ca");
    fakeApi({ [`GET ${URL}`]: NOT_FOUND });
    renderApp("/ca/profile");

    expect(await screen.findByRole("checkbox", { name: "GSTR-1" })).toHaveAttribute(
      "id",
      "specializations-gstr_1",
    );
    expect(screen.getByRole("checkbox", { name: "Hindi" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "gstr_1" })).not.toBeInTheDocument();
  });

  it("uploads the Certificate of Practice", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({
      [`GET ${URL}`]: [200, SAVED],
      [`POST ${URL}/certificate`]: [200, { ...SAVED, has_certificate: true }],
    });
    renderApp("/ca/profile");
    const user = userEvent.setup();

    const file = new File(["%PDF-1.4"], "cop.pdf", { type: "application/pdf" });
    await user.upload(await screen.findByLabelText("Certificate file"), file);
    await user.click(screen.getByRole("button", { name: "Upload certificate" }));

    expect(
      await screen.findByText("Certificate uploaded. An admin will check it."),
    ).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls.find(([path]) => path === `${URL}/certificate`);
    expect(init.body.get("file").name).toBe("cop.pdf");
  });

  it("warns a verified CA that a new number needs a new check", async () => {
    loginAs("ca");
    fakeApi({ [`GET ${URL}`]: [200, { ...SAVED, verification_status: "verified" }] });
    renderApp("/ca/profile");
    const user = userEvent.setup();

    const field = await screen.findByLabelText("ICAI membership number");
    expect(screen.queryByText(/goes back to an admin/)).not.toBeInTheDocument();
    await user.clear(field);
    await user.type(field, "654321");

    expect(screen.getByText(/goes back to an admin for verification/)).toBeInTheDocument();
  });

  it("shows a rejection's reason and a preview of the public profile", async () => {
    loginAs("ca");
    fakeApi({
      [`GET ${URL}`]: [
        200,
        { ...SAVED, verification_status: "rejected", rejection_reason: "The CoP number is wrong." },
      ],
    });
    renderApp("/ca/profile");

    expect(await screen.findByText("The CoP number is wrong.")).toBeInTheDocument();
    expect(screen.getByText("Preview: how businesses see you")).toBeInTheDocument();
    expect(screen.getByText("Free (pro-bono) slots per month")).toBeInTheDocument();
  });

  it("shows the setup checklist on the dashboard until verified", async () => {
    loginAs("ca");
    fakeApi({
      "GET /api/v1/ca-workspace/dashboard": [200, { message: "Welcome, Test ca" }],
      [`GET ${URL}`]: [
        200,
        { ...SAVED, verification_status: "rejected", rejection_reason: "Blurry certificate." },
      ],
      "GET /api/v1/marketplace/ca-services": [
        200,
        { items: [{ service_id: "s1", price: "700.00" }] },
      ],
    });
    renderApp("/ca");

    const checklist = await screen.findByRole("list", { name: "Setup checklist" });
    expect(checklist).toHaveTextContent("✓ Profile");
    expect(checklist).toHaveTextContent("✗ Certificate uploaded");
    expect(checklist).toHaveTextContent("✓ Prices set");
    expect(checklist).toHaveTextContent("Verification: Rejected (Blurry certificate.)");
  });
});
