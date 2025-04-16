import { File } from "../entities/index.js";
export interface ReadFileParams {
  projectName: string;
  fileName: string;
}

export interface ReadFileUseCase {
  readFile(params: ReadFileParams): Promise<File | null>;
}
