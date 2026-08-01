function writeResult(resultPath, result)
%WRITERESULT Atomically write a structured MATLAB result JSON file.

if ~(ischar(resultPath) || (isstring(resultPath) && isscalar(resultPath)))
    error("photonic:result:InvalidPath", "Result path must be a character vector or scalar string.");
end
resultPath = char(resultPath);
if ~endsWith(lower(resultPath), ".json")
    error("photonic:result:InvalidExtension", "Result path must end with .json.");
end
folder = fileparts(resultPath);
if isempty(folder)
    folder = pwd;
end
if ~isfolder(folder)
    [created, message] = mkdir(folder);
    if ~created
        error("photonic:result:CreateDirectory", ...
            "Result directory could not be created: %s", message);
    end
end

encoded = jsonencode(result);
temporaryPath = [tempname(folder) ".tmp"];
temporaryCleanup = onCleanup(@() removeTemporary(temporaryPath)); %#ok<NASGU>
fileId = fopen(temporaryPath, "w", "n", "UTF-8");
if fileId < 0
    error("photonic:result:Open", "Temporary result file could not be opened.");
end
fileCleanup = onCleanup(@() closeIfOpen(fileId)); %#ok<NASGU>
written = fwrite(fileId, encoded, "char");
if written ~= strlength(encoded)
    error("photonic:result:Write", "Result JSON was not written completely.");
end
fclose(fileId);
clear fileCleanup

[moved, message] = movefile(temporaryPath, resultPath, "f");
if ~moved
    error("photonic:result:Commit", "Result JSON could not be committed: %s", message);
end
end

function removeTemporary(pathValue)
if isfile(pathValue)
    delete(pathValue);
end
end

function closeIfOpen(fileId)
if ~isempty(fopen(fileId))
    fclose(fileId);
end
end
