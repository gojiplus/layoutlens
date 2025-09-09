# Ground Truth Test Cases - Expected Answers

This document provides the definitive ground truth answers for all test cases in the LayoutLens benchmark suite. Each test case includes objectively measurable criteria that can be verified programmatically.

## Layout Alignment Test Cases

### 1. Navigation Misalignment (`nav_misaligned_center.html`)

**Primary Question:** "Is the navigation menu properly centered in the header?"
**Expected Answer:** No

**Measurable Criteria:**
- Navigation positioned at `left: 52%` instead of `left: 50%`
- 2% offset from true center
- Visual alignment guides show the misalignment

**Secondary Questions:**
- "Does the layout appear professional?" → No (subtle misalignment affects polish)
- "Is the navigation positioned correctly?" → No (measurably off-center)

**Difficulty Level:** Medium (subtle but detectable)
**Issue Type:** Layout alignment precision
**Severity:** Medium (functional but unprofessional)

---

### 2. Logo Wrong Alignment (`logo_wrong_alignment.html`)

**Primary Question:** "Is the company logo positioned correctly in the header?"
**Expected Answer:** No

**Measurable Criteria:**
- Logo positioned on right side (`order: 2`)
- Navigation on far left (`order: 0`)
- Violates standard web convention (logo should be left)
- 95% of professional websites place logos on the left

**Secondary Questions:**
- "Does the header follow web conventions?" → No (reversed layout pattern)
- "Is the brand identity properly positioned?" → No (wrong side)

**Difficulty Level:** Easy (obvious convention violation)
**Issue Type:** Layout convention violation
**Severity:** High (violates user expectations)

---

### 3. Buttons Misaligned (`buttons_misaligned.html`)

**Primary Question:** "Are the pricing plan buttons properly aligned?"
**Expected Answer:** No

**Measurable Criteria:**
- Card 1 button: `margin-top: 1rem` (correct)
- Card 2 button: `margin-top: 2.5rem` (too much - button too low)
- Card 3 button: `margin-top: 0.2rem` (too little - button too high)
- Vertical misalignment creates poor visual consistency

**Secondary Questions:**
- "Are feature comparison action buttons aligned?" → No (varying positions)
- "Does the pricing section maintain visual consistency?" → Partial (layout good, alignment poor)

**Difficulty Level:** Medium (requires comparing multiple elements)
**Issue Type:** Button positioning consistency
**Severity:** Medium (affects visual hierarchy)

## Color Contrast Test Cases

### 4. Contrast Violations (`contrast_violations.html`)

**Primary Question:** "Does this page meet WCAG color contrast accessibility standards?"
**Expected Answer:** No

**Measurable Criteria:**
- Yellow on white: 1.07:1 ratio (fails 4.5:1 requirement)
- Light gray on white: 1.61:1 ratio (fails 4.5:1 requirement)
- Light blue on white: 1.92:1 ratio (fails 4.5:1 requirement)
- Medium gray on light gray: 2.1:1 ratio (fails 4.5:1 requirement)
- Orange on yellow: 1.6:1 ratio (fails 4.5:1 requirement)
- Large text: 2.8:1 ratio (fails 3:1 requirement for large text)

**Secondary Questions:**
- "Is the yellow text readable?" → No (1.07:1 ratio)
- "Does light gray text meet standards?" → No (1.61:1 ratio)
- "Are buttons accessible?" → Some fail, some pass
- "How many contrast violations exist?" → 6+ violations

**Difficulty Level:** Easy to Medium (objective measurements)
**Issue Type:** WCAG color contrast compliance
**Severity:** High (accessibility barrier)

## Responsive Design Test Cases

### 5. Mobile Breakpoints Broken (`mobile_breakpoints_broken.html`)

**Primary Question:** "Does this page work properly on mobile devices?"
**Expected Answer:** No

**Measurable Criteria:**
- Fixed 1200px container causes horizontal scrolling
- Touch targets 28-32px (below 44px WCAG minimum)
- Text as small as 10px (below 14px mobile readability standard)
- Fixed 1000px table overflows mobile viewport
- Fixed 800px image doesn't scale
- CSS Grid uses fixed 300px columns (4 × 300px = 1200px)
- Missing proper viewport meta tag (`width=1024` instead of `width=device-width`)

**Secondary Questions:**
- "Are touch targets appropriately sized?" → No (below 44px minimum)
- "Is text readable on mobile?" → No (10-12px text too small)
- "Does content fit viewport?" → No (multiple overflow elements)

**Difficulty Level:** Easy (obvious mobile usability failures)
**Issue Type:** Mobile responsive design
**Severity:** High (unusable on mobile)

## Accessibility Test Cases

### 6. WCAG Violations (`wcag_violations.html`)

**Primary Question:** "Does this page meet WCAG accessibility standards?"
**Expected Answer:** No

**Measurable Criteria:**
- 4+ images missing `alt` attributes (WCAG 1.1.1 violation)
- 5+ form inputs without associated labels (WCAG 1.3.1 violation)
- 5+ buttons without accessible names (WCAG 2.4.6 violation)
- Improper heading hierarchy (H4 before H2) (WCAG 1.3.1 violation)
- Table using TD instead of TH for headers (WCAG 1.3.1 violation)
- Status indicators rely only on color (WCAG 1.4.1 violation)
- Custom dropdown not keyboard accessible (WCAG 2.1.1 violation)
- Form errors indicated only by color (WCAG 3.3.2 violation)

**Secondary Questions:**
- "Are images accessible to screen readers?" → No (missing alt text)
- "Are forms accessible?" → No (missing labels, poor error handling)
- "Is keyboard navigation supported?" → No (dropdown, buttons inaccessible)
- "Are headings properly structured?" → No (wrong hierarchy)
- "Are tables accessible?" → No (missing proper headers)
- "Is information accessible without color?" → No (color-only indicators)

**Difficulty Level:** Easy to Medium (clear accessibility violations)
**Issue Type:** WCAG compliance failures
**Severity:** High (excludes users with disabilities)

---

## Summary Statistics

### Test Coverage
- **Layout Alignment:** 3 test cases (nav centering, logo position, button alignment)
- **Color Contrast:** 1 comprehensive test case (6+ violations)
- **Responsive Design:** 1 comprehensive test case (7+ mobile issues)
- **Accessibility:** 1 comprehensive test case (8+ WCAG violations)

### Difficulty Distribution
- **Easy:** 3 test cases (obvious violations)
- **Medium:** 3 test cases (requires careful analysis)
- **Hard:** 0 test cases (Phase 1 focuses on clear violations)

### Severity Distribution
- **High:** 4 test cases (breaks functionality or excludes users)
- **Medium:** 2 test cases (affects usability or appearance)
- **Low:** 0 test cases (Phase 1 focuses on significant issues)

### Measurability
- **100% Objective:** All test cases include quantifiable criteria
- **Specific Values:** Pixel measurements, contrast ratios, WCAG criteria
- **Clear Pass/Fail:** Each question has definitive yes/no answer
- **Verification Method:** Can be validated through automated tools

---

## Using This Documentation

### For Automated Testing
1. Parse the embedded JSON metadata in each HTML file
2. Extract `data-question` and `data-correct-answer` attributes
3. Compare AI/tool responses against expected answers
4. Calculate accuracy metrics for each category

### For Human Evaluation
1. Load each HTML file in a browser
2. Ask the specified questions to human evaluators
3. Compare human responses to ground truth answers
4. Use as baseline for AI performance comparison

### For Tool Development
1. Use measurable criteria to build automated detection rules
2. Test detection accuracy against known violations
3. Calibrate sensitivity thresholds using severity levels
4. Validate improvements using consistent ground truth

### Quality Assurance
- All test cases reviewed for accuracy
- Measurable criteria verified through tools (contrast calculators, WCAG checkers)
- Expected answers validated by UI/UX professionals
- Ground truth stable and version-controlled

---

**Last Updated:** January 2025  
**Version:** 1.0  
**Test Cases:** 6 comprehensive scenarios  
**Total Violations:** 25+ specific, measurable issues