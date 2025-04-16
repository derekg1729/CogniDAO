import { ListProjectFilesUseCase } from "../../../src/domain/usecases/list-project-files.js";
import { ListProjectFilesRequest } from "../../../src/presentation/controllers/list-project-files/protocols.js";

export class MockListProjectFilesUseCase implements ListProjectFilesUseCase {
  async listProjectFiles(params: ListProjectFilesRequest): Promise<string[]> {
    return ["file1.txt", "file2.txt"];
  }
}

export const makeListProjectFilesUseCase = (): ListProjectFilesUseCase => {
  return new MockListProjectFilesUseCase();
};
