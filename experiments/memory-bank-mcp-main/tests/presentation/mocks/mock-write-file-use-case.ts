import { WriteFileUseCase } from "../../../src/domain/usecases/write-file.js";
import { WriteRequest } from "../../../src/presentation/controllers/write/protocols.js";

export class MockWriteFileUseCase implements WriteFileUseCase {
  async writeFile(params: WriteRequest): Promise<string | null> {
    return null;
  }
}

export const makeWriteFileUseCase = (): WriteFileUseCase => {
  return new MockWriteFileUseCase();
};
