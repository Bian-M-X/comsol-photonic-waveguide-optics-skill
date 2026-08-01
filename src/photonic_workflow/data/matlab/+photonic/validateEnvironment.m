function inventory = validateEnvironment
%VALIDATEENVIRONMENT Return a redacted, structured local MATLAB inventory.

installedProducts = ver;
productTemplate = struct( ...
    "product_name", "", ...
    "release", "", ...
    "version", "", ...
    "installed", true, ...
    "license_verified", false);
products = repmat(productTemplate, numel(installedProducts), 1);
for index = 1:numel(installedProducts)
    products(index).product_name = installedProducts(index).Name;
    products(index).release = installedProducts(index).Release;
    products(index).version = installedProducts(index).Version;
end

productNames = string({installedProducts.Name});
inventory = struct;
inventory.schema_version = "1.0";
inventory.source = "photonic.validateEnvironment fixed local probe";
inventory.availability = "available";
inventory.root_alias = "<matlab-root>";
inventory.release = version("-release");
inventory.version = version;
inventory.platform = computer;
inventory.architecture = computer("arch");
inventory.batch_capable = true;
inventory.complete_product_inventory = true;
inventory.products = products;
inventory.community_toolboxes = struct([]);
inventory.comsol_livelink = "unverified";
inventory.lumerical_api = "unverified";
inventory.instrument_control = availabilityForProduct( ...
    productNames, "Instrument Control Toolbox");
inventory.simulink = availabilityForProduct(productNames, "Simulink");
inventory.redacted = true;
end

function status = availabilityForProduct(productNames, expectedName)
if any(strcmpi(productNames, expectedName))
    status = "available";
else
    status = "unavailable";
end
end
