import { ReadFile } from "../../../data/usecases/read-file/read-file.js";
import { FsFileRepository } from "../../../infra/filesystem/index.js";
import { FsProjectRepository } from "../../../infra/filesystem/repositories/fs-project-repository.js";
import { env } from "../../config/env.js";

export const makeReadFile = () => {
  const projectRepository = new FsProjectRepository(env.rootPath);
  const fileRepository = new FsFileRepository(env.rootPath);

  return new ReadFile(fileRepository, projectRepository);
};
