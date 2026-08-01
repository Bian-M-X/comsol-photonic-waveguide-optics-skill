function photonic_batch_wrapper
%PHOTONIC_BATCH_WRAPPER Fixed, non-interactive entry for controlled batch runs.

runSpecPath = getenv("PHOTONIC_RUN_SPEC");
resultPath = getenv("PHOTONIC_RESULT_PATH");
entryRoot = getenv("PHOTONIC_MATLAB_ENTRY_ROOT");

if strlength(runSpecPath) == 0 || strlength(resultPath) == 0 || strlength(entryRoot) == 0
    error("photonic:batch:MissingEnvironment", ...
        "The controlled PHOTONIC_RUN_SPEC, PHOTONIC_RESULT_PATH and " + ...
        "PHOTONIC_MATLAB_ENTRY_ROOT values are required.");
end
if ~isfolder(entryRoot)
    error("photonic:batch:MissingEntryRoot", ...
        "The configured fixed MATLAB entry root is unavailable.");
end

addpath(entryRoot, "-begin");
pathCleanup = onCleanup(@() removeEntryRoot(entryRoot)); %#ok<NASGU>
photonic.entry(runSpecPath, resultPath);
end

function removeEntryRoot(entryRoot)
if contains([path pathsep], [char(entryRoot) pathsep])
    rmpath(entryRoot);
end
end
