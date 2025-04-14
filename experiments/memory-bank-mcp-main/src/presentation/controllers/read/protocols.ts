import { ReadFileUseCase } from "../../../domain/usecases/read-file.js";
import { NotFoundError } from "../../errors/index.js";
import {
  Controller,
  Request,
  Response,
  Validator,
} from "../../protocols/index.js";
export interface ReadRequest {
  /**
   * The name of the project containing the file.
   */
  projectName: string;

  /**
   * The name of the file to read.
   */
  fileName: string;
}

export type ReadResponse = string;

export {
  Controller,
  NotFoundError,
  ReadFileUseCase,
  Request,
  Response,
  Validator,
};
