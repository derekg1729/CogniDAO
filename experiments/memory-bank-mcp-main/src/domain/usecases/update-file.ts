import { File } from "../entities/index.js";

export interface UpdateFileParams {
  projectName: string;
  fileName: string;
  content: string;
}

export interface UpdateFileUseCase {
  updateFile(params: UpdateFileParams): Promise<File | null>;
}
