classdef TestPhotonicRuntime < matlab.unittest.TestCase
    methods (Test)
        function validateEnvironmentIsRedactedAndStructured(testCase)
            inventory = photonic.validateEnvironment;
            testCase.verifyEqual(string(inventory.root_alias), "<matlab-root>");
            testCase.verifyTrue(inventory.batch_capable);
            testCase.verifyTrue(inventory.complete_product_inventory);
            testCase.verifyNotEmpty(inventory.release);
            testCase.verifyNotEmpty(inventory.products);
        end

        function fixedEntryWritesExecutionOnlyResult(testCase)
            fixtureRoot = tempname;
            mkdir(fixtureRoot);
            fixtureCleanup = onCleanup(@() rmdir(fixtureRoot, "s")); %#ok<NASGU>
            runSpecPath = fullfile(fixtureRoot, "run-spec.json");
            resultPath = fullfile(fixtureRoot, "result.json");
            runSpec = TestPhotonicRuntime.baseRunSpec;
            TestPhotonicRuntime.writeJson(runSpecPath, runSpec);

            photonic.entry(runSpecPath, resultPath);
            result = jsondecode(fileread(resultPath));

            testCase.verifyEqual(string(result.contract_type), "MatlabResultManifest");
            testCase.verifyEqual(string(result.execution_status), "succeeded");
            testCase.verifyEqual(result.exit_code, 0);
            testCase.verifyEqual(string(result.validity), "unknown");
            testCase.verifyNotEmpty(result.matlab_release);
        end

        function arbitraryEntrypointIdIsRejected(testCase)
            fixtureRoot = tempname;
            mkdir(fixtureRoot);
            fixtureCleanup = onCleanup(@() rmdir(fixtureRoot, "s")); %#ok<NASGU>
            runSpecPath = fullfile(fixtureRoot, "unsafe-run-spec.json");
            runSpec = TestPhotonicRuntime.baseRunSpec;
            runSpec.entrypoint_id = "user.supplied.function";
            TestPhotonicRuntime.writeJson(runSpecPath, runSpec);

            testCase.verifyError( ...
                @() photonic.readRunSpec(runSpecPath), ...
                "photonic:runSpec:UnsafeEntry");
        end
    end

    methods (Static, Access = private)
        function runSpec = baseRunSpec
            runSpec = struct;
            runSpec.contract_type = "MatlabRunSpec";
            runSpec.schema_version = "1.0";
            runSpec.stable_id = "matlab-run:matlab-unittest";
            runSpec.name = "MATLAB runtime unit test";
            runSpec.source = "repository MATLAB unit test";
            runSpec.operation = "environment.validate";
            runSpec.entrypoint_id = "photonic.environment.validate.v1";
            runSpec.dry_run = true;
        end

        function writeJson(pathValue, payload)
            fileId = fopen(pathValue, "w", "n", "UTF-8");
            if fileId < 0
                error("photonic:test:FixtureWrite", "Cannot open test fixture.");
            end
            cleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
            fwrite(fileId, jsonencode(payload), "char");
        end
    end
end
