function runSpec = readRunSpec(runSpecPath)
%READRUNSPEC Read and fail-closed validate the fixed MATLAB RunSpec JSON.

if ~(ischar(runSpecPath) || (isstring(runSpecPath) && isscalar(runSpecPath)))
    error("photonic:runSpec:InvalidPath", "RunSpec path must be a character vector or scalar string.");
end
runSpecPath = char(runSpecPath);
if ~endsWith(lower(runSpecPath), ".json")
    error("photonic:runSpec:InvalidExtension", "RunSpec must be a JSON file.");
end
if ~isfile(runSpecPath)
    error("photonic:runSpec:Missing", "RunSpec JSON is unavailable.");
end
fileInfo = dir(runSpecPath);
if isempty(fileInfo) || fileInfo.bytes > 16 * 1024 * 1024
    error("photonic:runSpec:Size", "RunSpec JSON exceeds the controlled 16 MiB limit.");
end

try
    runSpec = jsondecode(fileread(runSpecPath));
catch exception
    error("photonic:runSpec:InvalidJson", "RunSpec JSON could not be decoded: %s", exception.identifier);
end
if ~isstruct(runSpec) || ~isscalar(runSpec)
    error("photonic:runSpec:InvalidRoot", "RunSpec JSON root must be one object.");
end

requiredFields = ["contract_type", "stable_id", "operation", "entrypoint_id", "dry_run"];
for fieldName = requiredFields
    fieldNameChar = char(fieldName);
    if ~isfield(runSpec, fieldNameChar)
        error("photonic:runSpec:MissingField", ...
            "RunSpec is missing required field %s.", fieldNameChar);
    end
end
if ~strcmp(string(runSpec.contract_type), "MatlabRunSpec")
    error("photonic:runSpec:WrongContract", "RunSpec contract_type must be MatlabRunSpec.");
end
if ~strcmp(string(runSpec.entrypoint_id), "photonic.environment.validate.v1")
    error("photonic:runSpec:UnsafeEntry", "The entrypoint ID is not registered.");
end
if ~strcmp(string(runSpec.operation), "environment.validate")
    error("photonic:runSpec:UnsupportedOperation", ...
        "The requested MATLAB operation is not implemented in Phase A.");
end
if ~(islogical(runSpec.dry_run) && isscalar(runSpec.dry_run) && runSpec.dry_run)
    error("photonic:runSpec:ExecutionUnverified", ...
        "Phase A fixed entry accepts dry-run RunSpecs only.");
end
end
