import { File } from "../../domain/entities/index.js";

export interface FileRepository {
  listFiles(projectName: string): Promise<File[]>;
  loadFile(projectName: string, fileName: string): Promise<File | null>;
  writeFile(
    projectName: string,
    fileName: string,
    content: string
  ): Promise<File | null>;
  updateFile(
    projectName: string,
    fileName: string,
    content: string
  ): Promise<File | null>;
}
