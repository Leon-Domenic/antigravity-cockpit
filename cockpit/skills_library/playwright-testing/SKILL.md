---
name: playwright-testing
description: End-to-end browser automation and testing with Playwright, including headless navigation, screenshot comparisons, and robust locators.
---

# Playwright E2E Automation

## Overview
Cross-browser end-to-end testing and browser automation for web apps.

## Rules & Patterns
1. Prefer resilient user-facing locators: getByRole, getByText, getByLabel.
2. Avoid hardcoded timeouts; rely on auto-waiting assertions like wait expect(locator).toBeVisible().
3. Capture traces and screenshots on test failure.