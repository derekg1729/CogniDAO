import {
  FileRepository,
  ProjectRepository,
  WriteFileParams,
  WriteFileUseCase,
} from "./write-file-protocols.js";

export class WriteFile implements WriteFileUseCase {
  constructor(
    private readonly fileRepository: FileRepository,
    private readonly projectRepository: ProjectRepository
  ) {}

  async writeFile(params: WriteFileParams): Promise<string | null> {
    const { projectName, fileName, content } = params;

    await this.projectRepository.ensureProject(projectName);

    const existingFile = await this.fileRepository.loadFile(
      projectName,
      fileName
    );
    if (existingFile !== null) {
      return null;
    }

    await this.fileRepository.writeFile(projectName, fileName, content);
    return await this.fileRepository.loadFile(projectName, fileName);
  }
}
