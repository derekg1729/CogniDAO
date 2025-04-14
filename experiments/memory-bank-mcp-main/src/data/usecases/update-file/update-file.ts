import {
  FileRepository,
  ProjectRepository,
  UpdateFileParams,
  UpdateFileUseCase,
} from "./update-file-protocols.js";

export class UpdateFile implements UpdateFileUseCase {
  constructor(
    private readonly fileRepository: FileRepository,
    private readonly projectRepository: ProjectRepository
  ) {}

  async updateFile(params: UpdateFileParams): Promise<string | null> {
    const { projectName, fileName, content } = params;

    const projectExists = await this.projectRepository.projectExists(
      projectName
    );
    if (!projectExists) {
      return null;
    }

    const existingFile = await this.fileRepository.loadFile(
      projectName,
      fileName
    );
    if (existingFile === null) {
      return null;
    }

    await this.fileRepository.updateFile(projectName, fileName, content);
    return await this.fileRepository.loadFile(projectName, fileName);
  }
}
