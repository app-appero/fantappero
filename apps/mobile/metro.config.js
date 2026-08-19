const { getDefaultConfig } = require("expo/metro-config");
const path = require("node:path");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);

config.watchFolders = [workspaceRoot];
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];
config.resolver.disableHierarchicalLookup = true;

/** Workspace packages use TS ESM imports with a `.js` extension; Metro needs `.ts`/`.tsx`. */
const TS_SOURCE_EXTENSIONS = [".ts", ".tsx"];
const defaultResolveRequest = config.resolver.resolveRequest;

config.resolver.resolveRequest = (context, moduleName, platform) => {
  const resolveModule = (name) =>
    defaultResolveRequest
      ? defaultResolveRequest(context, name, platform)
      : context.resolveRequest(context, name, platform);

  if (moduleName.startsWith(".") && moduleName.endsWith(".js")) {
    const baseName = moduleName.slice(0, -3);
    for (const extension of TS_SOURCE_EXTENSIONS) {
      try {
        return resolveModule(`${baseName}${extension}`);
      } catch {
        // try next extension
      }
    }
  }

  return resolveModule(moduleName);
};

module.exports = config;
