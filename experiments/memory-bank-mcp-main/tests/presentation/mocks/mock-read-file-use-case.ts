import { ReadFileUseCase } from "../../../src/domain/usecases/read-file.js";
import { ReadRequest } from "../../../src/presentation/controllers/read/protocols.js";

export class MockReadFileUseCase implements ReadFileUseCase {
  async readFile(params: ReadRequest): Promise<string | null> {
    return "file content";
  }
}

export const makeReadFileUseCase = (): ReadFileUseCase => {
  return new MockReadFileUseCase();
};
