import { File } from "../entities/index.js";
export interface WriteFileParams {
  projectName: string;
  fileName: string;
  content: string;
}

export interface WriteFileUseCase {
  writeFile(params: WriteFileParams): Promise<File | null>;
}
