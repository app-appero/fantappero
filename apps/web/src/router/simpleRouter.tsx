import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type AnchorHTMLAttributes,
  type ReactNode,
} from "react";

type RouterContextValue = {
  pathname: string;
  search: string;
  navigate: (to: string, options?: { replace?: boolean }) => void;
};

const RouterContext = createContext<RouterContextValue | null>(null);

function subscribe(callback: () => void) {
  window.addEventListener("popstate", callback);
  return () => window.removeEventListener("popstate", callback);
}

function getSnapshot() {
  return `${window.location.pathname}${window.location.search}`;
}

function getServerSnapshot() {
  return "/";
}

export type BrowserRouterProps = {
  children: ReactNode;
};

export function BrowserRouter({ children }: BrowserRouterProps) {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const navigate = useCallback((to: string, options?: { replace?: boolean }) => {
    if (options?.replace) {
      window.history.replaceState(null, "", to);
    } else {
      window.history.pushState(null, "", to);
    }
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, []);

  const value = useMemo<RouterContextValue>(() => {
    const question = snapshot.indexOf("?");
    if (question === -1) {
      return { pathname: snapshot, search: "", navigate };
    }
    return {
      pathname: snapshot.slice(0, question),
      search: snapshot.slice(question),
      navigate,
    };
  }, [snapshot, navigate]);

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export type MemoryRouterProps = {
  initialEntries: string[];
  children: ReactNode;
};

/** Test-only in-memory router (single entry, no history stack). */
export function MemoryRouter({ initialEntries, children }: MemoryRouterProps) {
  const entry = initialEntries[0] ?? "/";
  const question = entry.indexOf("?");
  const pathname = question === -1 ? entry : entry.slice(0, question);
  const search = question === -1 ? "" : entry.slice(question);

  const navigate = useCallback(() => undefined, []);

  const value = useMemo<RouterContextValue>(
    () => ({ pathname, search, navigate }),
    [pathname, search, navigate],
  );

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

function useRouter(): RouterContextValue {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error("Router hooks must be used within BrowserRouter or MemoryRouter");
  }
  return context;
}

export function useLocation() {
  const { pathname, search } = useRouter();
  return useMemo(() => ({ pathname, search }), [pathname, search]);
}

export function useNavigate() {
  return useRouter().navigate;
}

export function useSearchParams(): [URLSearchParams, (next: URLSearchParams) => void] {
  const { search, navigate, pathname } = useRouter();
  const params = useMemo(() => new URLSearchParams(search), [search]);
  const setParams = useCallback(
    (next: URLSearchParams) => {
      const query = next.toString();
      navigate(query ? `${pathname}?${query}` : pathname, { replace: true });
    },
    [navigate, pathname],
  );
  return [params, setParams];
}

export type RouteMatch = {
  params: Record<string, string>;
  pathname: string;
};

function matchPath(pattern: string, pathname: string): RouteMatch | null {
  const patternParts = pattern.split("/").filter(Boolean);
  const pathParts = pathname.split("/").filter(Boolean);

  if (patternParts.length !== pathParts.length) {
    return null;
  }

  const params: Record<string, string> = {};
  for (let i = 0; i < patternParts.length; i += 1) {
    const patternPart = patternParts[i];
    const pathPart = pathParts[i];
    if (!patternPart || pathPart === undefined) {
      return null;
    }
    if (patternPart.startsWith(":")) {
      params[patternPart.slice(1)] = pathPart;
    } else if (patternPart !== pathPart) {
      return null;
    }
  }

  return { params, pathname };
}

type RouteObject = {
  path?: string;
  element?: ReactNode;
  children?: RouteObject[];
};

type FlatRoute = {
  fullPath: string;
  element: ReactNode;
};

function flattenRoutes(routes: RouteObject[], parentPath = ""): FlatRoute[] {
  const flat: FlatRoute[] = [];
  for (const route of routes) {
    const segment = route.path ?? "";
    const fullPath =
      segment === "*"
        ? "*"
        : [parentPath, segment].filter(Boolean).join("/").replace(/\/+/g, "/") || "/";

    if (route.element) {
      flat.push({ fullPath: fullPath.startsWith("/") ? fullPath : `/${fullPath}`, element: route.element });
    }
    if (route.children) {
      flat.push(...flattenRoutes(route.children, fullPath === "/" ? "" : fullPath));
    }
  }
  return flat;
}

export type RoutesProps = {
  children: ReactNode;
};

export function Routes({ children }: RoutesProps) {
  const { pathname } = useLocation();
  const routes = useMemo(() => {
    const items: RouteObject[] = [];
    const childArray = Array.isArray(children) ? children : [children];
    for (const child of childArray) {
      if (child && typeof child === "object" && "props" in child) {
        items.push(child.props as RouteObject);
      }
    }
    return flattenRoutes(items);
  }, [children]);

  const exact = routes.find((route) => route.fullPath === pathname);
  if (exact) {
    return <>{exact.element}</>;
  }

  const wildcard = routes.find((route) => route.fullPath === "*");
  if (wildcard) {
    return <>{wildcard.element}</>;
  }

  return null;
}

export type RouteProps = RouteObject;

export function Route(_props: RouteProps) {
  return null;
}

export type NavigateProps = {
  to: string;
  replace?: boolean;
  state?: unknown;
};

export function Navigate({ to, replace }: NavigateProps) {
  const { navigate } = useRouter();
  navigate(to, { replace });
  return null;
}

export type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  to: string;
};

export function Link({ to, href, onClick, ...rest }: LinkProps) {
  const { navigate } = useRouter();
  return (
    <a
      href={to}
      {...rest}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey) {
          event.preventDefault();
          navigate(to);
        }
      }}
    />
  );
}

export type NavLinkProps = Omit<LinkProps, "className"> & {
  className?: string | ((state: { isActive: boolean }) => string);
};

export function NavLink({ to, className, ...rest }: NavLinkProps) {
  const { pathname } = useLocation();
  const isActive = pathname === to || pathname.startsWith(`${to}/`);
  const resolvedClass =
    typeof className === "function" ? className({ isActive }) : className;

  return <Link to={to} className={resolvedClass} aria-current={isActive ? "page" : undefined} {...rest} />;
}

export function Outlet() {
  return null;
}

export function useOutletContext<T>(): T {
  return {} as T;
}

/** Layout route helper — renders parent layout when child path matches prefix. */
export type LayoutRouteProps = {
  element: ReactNode;
  children: ReactNode;
};

export function LayoutRoute({ element, children }: LayoutRouteProps) {
  const { pathname } = useLocation();
  const childRoutes = useMemo(() => {
    const items: RouteObject[] = [];
    const childArray = Array.isArray(children) ? children : [children];
    for (const child of childArray) {
      if (child && typeof child === "object" && "props" in child) {
        items.push(child.props as RouteObject);
      }
    }
    return flattenRoutes(items);
  }, [children]);

  const child = childRoutes.find((route) => {
    if (route.fullPath === "*") {
      return true;
    }
    return matchPath(route.fullPath, pathname) ?? route.fullPath === pathname;
  });

  if (!child) {
    return null;
  }

  return (
    <>
      {element}
      {child.element}
    </>
  );
}
