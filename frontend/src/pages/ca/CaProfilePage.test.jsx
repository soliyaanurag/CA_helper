import { screen } from "@testing-library/react";
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

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Another CA has already registered this membership number.",
    );
  });
});
