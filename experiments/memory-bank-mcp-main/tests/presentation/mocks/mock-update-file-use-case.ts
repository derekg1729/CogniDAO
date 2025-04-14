import { UpdateFileUseCase } from "../../../src/domain/usecases/update-file.js";
import { UpdateRequest } from "../../../src/presentation/controllers/update/protocols.js";

export class MockUpdateFileUseCase implements UpdateFileUseCase {
  async updateFile(params: UpdateRequest): Promise<string | null> {
    return "updated content";
  }
}

export const makeUpdateFileUseCase = (): UpdateFileUseCase => {
  return new MockUpdateFileUseCase();
};
