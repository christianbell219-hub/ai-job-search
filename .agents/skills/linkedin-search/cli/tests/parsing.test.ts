import { describe, test, expect } from "bun:test";
import { parseJobCards, parseJobDetail, extractDivContent, minutesToTPR } from "../src/helpers";

// Minimal search-card markup: parseJobCards splits on the job-posting URN and
// needs an id, a base-search-card__title, and a full-link. Everything else is
// optional. We inject HTML entities into the title/company to exercise decoding.
function searchCard(id: string, title: string, company = "Acme"): string {
  return `<li>
    <div data-entity-urn="urn:li:jobPosting:${id}">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/${id}"></a>
      <h3 class="base-search-card__title">${title}</h3>
      <h4 class="base-search-card__subtitle"><a href="https://www.linkedin.com/company/acme">${company}</a></h4>
    </div>
  </li>`;
}

describe("decodeHtmlEntities (via parseJobCards)", () => {
  test("decodes hexadecimal numeric entities (&#xE9;)", () => {
    const [card] = parseJobCards(searchCard("123", "Caf&#xE9; Manager"));
    expect(card.title).toBe("Café Manager");
  });

  test("decodes uppercase-X hexadecimal entities (&#X...;)", () => {
    const [card] = parseJobCards(searchCard("124", "Deb&#XFC;t Role")); // &#XFC; = ü
    expect(card.title).toBe("Debüt Role");
  });

  test("still decodes decimal numeric entities (&#233;) — regression", () => {
    const [card] = parseJobCards(searchCard("125", "Caf&#233; Lead"));
    expect(card.title).toBe("Café Lead");
  });

  test("decodes supplementary-plane code points with fromCodePoint (&#128512;)", () => {
    const [card] = parseJobCards(searchCard("126", "Growth &#128512;"));
    expect(card.title).toBe("Growth 😀");
  });

  test("decodes hex supplementary-plane code points (&#x1F600;)", () => {
    const [card] = parseJobCards(searchCard("127", "Growth &#x1F600;"));
    expect(card.title).toBe("Growth 😀");
  });

  test("decodes hex entities in the company subtitle too", () => {
    const [card] = parseJobCards(searchCard("128", "Engineer", "N&#xF8;rrebro ApS"));
    expect(card.company).toBe("Nørrebro ApS");
  });
});

describe("decodeHtmlEntities (via parseJobDetail)", () => {
  test("decodes hex entities inside the job title", () => {
    const html = `<h1 class="topcard__title">Se&#xF1;or Engineer</h1>`;
    const job = parseJobDetail(html, "999");
    expect(job.title).toBe("Señor Engineer");
  });
});

describe("extractDivContent", () => {
  test("extracts content from simple div", () => {
    const html = '<div class="description__text">Simple text</div>';
    expect(extractDivContent(html, "description__text")).toBe("Simple text");
  });

  test("extracts content with nested divs — the regression case", () => {
    const html = `<div class="description__text">
      <div>Requirements:</div>
      <ul><li>Skill A</li></ul>
      <div>About Us:</div>
      <p>We are...</p>
    </div>`;
    expect(extractDivContent(html, "description__text")).toBe(
      '\n      <div>Requirements:</div>\n      <ul><li>Skill A</li></ul>\n      <div>About Us:</div>\n      <p>We are...</p>\n    ',
    );
  });

  test("returns null when class not found", () => {
    expect(extractDivContent("<div>no class</div>", "nonexistent")).toBeNull();
  });

  test("works with show-more-less-html__markup class", () => {
    const html = '<div class="show-more-less-html__markup">LinkedIn content</div>';
    expect(extractDivContent(html, "show-more-less-html__markup")).toBe("LinkedIn content");
  });

  test("handles deeply nested divs (3 levels)", () => {
    const html = `<div class="description__text">
      <div>
        <div>Deep content</div>
      </div>
    </div>`;
    expect(extractDivContent(html, "description__text")).toBe(
      '\n      <div>\n        <div>Deep content</div>\n      </div>\n    ',
    );
  });

  test("handles empty content", () => {
    const html = '<div class="description__text"></div>';
    expect(extractDivContent(html, "description__text")).toBe("");
  });

  test("parseJobDetail uses extractDivContent and preserves full description", () => {
    const html = `<div class="description__text">
      <div>Requirements:</div>
      <ul><li>5 years Python</li></ul>
      <div>About Us:</div>
      <p>We are hiring!</p>
    </div>`;
    const job = parseJobDetail(html, "999");
    expect(job.description).toContain("Requirements:");
    expect(job.description).toContain("5 years Python");
    expect(job.description).toContain("About Us:");
    expect(job.description).toContain("We are hiring!");
  });
});

describe("minutesToTPR", () => {
  test("converts minutes to an f_TPR seconds window", () => {
    expect(minutesToTPR(30)).toBe("r1800");
    expect(minutesToTPR(1)).toBe("r60");
    expect(minutesToTPR(1440)).toBe("r86400"); // matches jobageToTPR(1)
  });

  test("returns null for non-positive input", () => {
    expect(minutesToTPR(0)).toBeNull();
    expect(minutesToTPR(-5)).toBeNull();
  });
});

describe("parseHiringTeam (via parseJobDetail)", () => {
  test("returns null when guest HTML has no hiring-team block", () => {
    const html = `<h1 class="topcard__title">Engineer</h1>
      <a href="https://www.linkedin.com/in/random-person">Random</a>`;
    const job = parseJobDetail(html, "999");
    expect(job.hiringTeam).toBeNull();
  });

  test("parses a hirer-card name, title, and profile URL", () => {
    const html = `<h1 class="topcard__title">Engineer</h1>
      <section class="core-section-container hiring-team">
        <h2>Meet the hiring team</h2>
        <div class="hirer-card">
          <a class="hirer-card__name" href="https://www.linkedin.com/in/jane-doe">Jane Doe</a>
          <div class="hirer-card__job-title">Engineering Manager</div>
        </div>
      </section>`;
    const job = parseJobDetail(html, "999");
    expect(job.hiringTeam).toEqual([
      {
        name: "Jane Doe",
        title: "Engineering Manager",
        profileUrl: "https://www.linkedin.com/in/jane-doe",
      },
    ]);
  });

  test("does not treat description /in/ links as the hiring team", () => {
    const html = `<h1 class="topcard__title">Engineer</h1>
      <div class="show-more-less-html__markup">See <a href="https://www.linkedin.com/in/someone">someone</a></div>`;
    const job = parseJobDetail(html, "999");
    expect(job.hiringTeam).toBeNull();
  });
});

describe("parseClosedJob (via parseJobDetail)", () => {
  test("open posting is not closed", () => {
    const html = `<h1 class="topcard__title">Engineer</h1>
      <div class="show-more-less-html__markup">We are hiring a backend engineer.</div>`;
    const job = parseJobDetail(html, "999");
    expect(job.closed).toBe(false);
    expect(job.closedReason).toBeNull();
  });

  test("detects no longer accepting applications", () => {
    const html = `<h1 class="topcard__title">Engineer</h1>
      <span>No longer accepting applications</span>`;
    const job = parseJobDetail(html, "999");
    expect(job.closed).toBe(true);
    expect(job.closedReason).toBe("no longer accepting applications");
  });

  test("detects no longer available", () => {
    const html = `<div>This job is no longer available</div>`;
    const job = parseJobDetail(html, "999");
    expect(job.closed).toBe(true);
    expect(job.closedReason).toBe("no longer available");
  });

  test("empty HTML is closed as not found", () => {
    const job = parseJobDetail("", "999");
    expect(job.closed).toBe(true);
    expect(job.closedReason).toBe("not found");
  });
});
