# Target venue (Feature 18, Stage C)

**Venue:** EOOLT -- the International Workshop on Equation-Based
Object-Oriented Modeling Languages and Tools (10th edition, EOOLT 2026).
Chosen because it is the most directly on-topic real venue for this
project's actual subject matter (code generation, verification, and
tooling for equation-based object-oriented modeling languages --
exactly what this project builds on top of Modelica/Rumoca), not a
generic systems or PL venue this work would need to be reframed for.

- **Location / date:** Bielefeld, Germany, June 15, 2026.
- **Track:** Full contributions (up to 10 pages) or shorter
  work-in-progress papers (up to 4 pages). This project targets the
  **full contribution** track -- the work has real, measured results
  across two stages (generality and scale), not an in-progress sketch.
- **Format:** ACM SigConf template (`\documentclass[sigconf]{acmart}`),
  published in the ACM International Conference Proceeding Series (ICPS).
- **Page limit:** 10 pages for full contributions (EasyChair CFP:
  "up to 10 pages for consideration by the program committee").
- **Submission deadline (2026 edition):** April 7, 2026 (title/abstract
  and full paper both due this date, per the EOOLT 2026 EasyChair CFP).

**Honest disclosure, not glossed over:** this deadline has already
passed as of this project's own timeline. This is a real constraint
this project cannot retroactively satisfy -- recorded here rather than
hidden, per this project's own discipline (`prd-combined.md` Section 7).
The venue and its template/page-limit are still adopted as the
structural target for Feature 19's restructure, since EOOLT's format is
stable year to year and the same venue (a future edition -- EOOLT 2027
or later, not yet announced with dates as of this search, August 2026)
is the realistic actual submission target once this work is complete.
Feature 23 ("Internal review and submission") was already scoped, before
this feature was reached, as stopping at "fully prepared to submit" --
this project cannot create accounts, pay fees, or literally submit to a
real venue on the user's behalf.

**Sources (fetched during this session, not fabricated):**
- https://eoolt.org/2026/index.html -- workshop dates, submission deadlines, paper types, ACM ICPS publication
- https://easychair.org/cfp/eoolt-2026 -- exact page limits (10 pages full / 4 pages WIP) and ACM SigConf template requirement
- https://discourse.julialang.org/t/cfp-eoolt-2026-10th-international-workshop-on-equation-based-object-oriented-modeling-languages-and-tools/135956 -- corroborating CFP announcement

**Template setup status (as of this entry): NOT YET DONE.** Confirmed a
local MiKTeX install can compile `\documentclass[sigconf]{acmart}` to
PDF (one missing dependency, `xstring`, needed an explicit
`miktex packages install xstring` first -- MiKTeX's automatic
package-install did not trigger it under `pdflatex -interaction=
nonstopmode` alone). Porting `docs/paper.md`'s actual content into that
template (a `paper/` directory, confirmed to build) is the remaining
Feature 18 work, not yet started.
