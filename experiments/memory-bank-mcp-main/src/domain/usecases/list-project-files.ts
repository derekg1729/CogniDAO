import { File } from "../entities/index.js";
export interface ListProjectFilesParams {
  projectName: string;
}

export interface ListProjectFilesUseCase {
  listProjectFiles(params: ListProjectFilesParams): Promise<File[]>;
}
