// React 19 warns "not configured to support act(...)" unless this flag is set,
// which @testing-library/react sets internally but raw createRoot()+act() tests do not.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
