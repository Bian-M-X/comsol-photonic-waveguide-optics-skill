function photonic_test_wrapper
%PHOTONIC_TEST_WRAPPER Run only the repository-owned MATLAB unit tests.

entryRoot = getenv("PHOTONIC_MATLAB_ENTRY_ROOT");
if strlength(entryRoot) == 0
    entryRoot = fileparts(fileparts(mfilename("fullpath")));
end
if ~isfolder(entryRoot)
    error("photonic:test:MissingEntryRoot", ...
        "PHOTONIC_MATLAB_ENTRY_ROOT must identify the reviewed MATLAB entry root.");
end

addpath(entryRoot, "-begin");
pathCleanup = onCleanup(@() removeEntryRoot(entryRoot)); %#ok<NASGU>
suite = testsuite(fullfile(entryRoot, "tests"));
results = run(suite);
disp(table(results));
if any([results.Failed])
    error("photonic:test:Failure", "One or more fixed MATLAB unit tests failed.");
end
end

function removeEntryRoot(entryRoot)
if contains([path pathsep], [char(entryRoot) pathsep])
    rmpath(entryRoot);
end
end
