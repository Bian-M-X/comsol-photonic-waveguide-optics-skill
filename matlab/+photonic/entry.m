function result = entry(runSpecPath, resultPath)
%ENTRY Fixed package entry point for controlled MATLAB batch operations.

started = tic;
runSpec = photonic.readRunSpec(runSpecPath);
result = baseResult(runSpec);
try
    switch string(runSpec.operation)
        case "environment.validate"
            inventory = photonic.validateEnvironment;
            result.matlab_release = inventory.release;
            result.toolbox_versions = toolboxVersionMap(inventory.products);
        otherwise
            error("photonic:entry:UnsupportedOperation", ...
                "The requested operation is not implemented in Phase A.");
    end
    result.execution_status = "succeeded";
    result.exit_code = 0;
    result.status = "succeeded";
catch exception
    result.execution_status = "failed";
    result.exit_code = 1;
    result.status = "failed";
    result.errors = {exception.identifier, redactMessage(exception.message)};
    result.duration_s = toc(started);
    photonic.writeResult(resultPath, result);
    rethrow(exception);
end
result.duration_s = toc(started);
photonic.writeResult(resultPath, result);
end

function result = baseResult(runSpec)
result = struct;
result.contract_type = "MatlabResultManifest";
result.schema_version = "1.0";
result.stable_id = string(runSpec.stable_id);
result.name = "MATLAB result for " + string(runSpec.stable_id);
result.revision = "1";
result.source = "photonic.entry fixed MATLAB batch entry";
result.created_at = string(datetime("now", ...
    "TimeZone", "UTC", ...
    "Format", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"));
result.provenance = {"fixed photonic.entry dispatch; no eval or arbitrary function name"};
result.status = "running";
result.validity = "unknown";
result.run_id = string(runSpec.stable_id);
result.execution_status = "running";
result.exit_code = [];
result.duration_s = [];
result.matlab_release = "";
result.toolbox_versions = struct;
result.artifacts = struct([]);
result.warnings = {};
result.errors = {};
result.log_path = "matlab.log";
end

function versions = toolboxVersionMap(products)
versions = struct;
for index = 1:numel(products)
    fieldName = matlab.lang.makeValidName(products(index).product_name);
    versions.(fieldName) = products(index).version;
end
end

function message = redactMessage(message)
message = string(message);
rootValue = string(matlabroot);
if strlength(rootValue) > 0
    message = replace(message, rootValue, "<matlab-root>");
end
userProfile = string(getenv("USERPROFILE"));
if strlength(userProfile) > 0
    message = replace(message, userProfile, "<user-profile>");
end
message = char(message);
end
