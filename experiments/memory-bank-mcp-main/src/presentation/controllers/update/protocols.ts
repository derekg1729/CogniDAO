import { UpdateFileUseCase } from "../../../domain/usecases/update-file.js";
import { NotFoundError } from "../../errors/index.js";
import {
  Controller,
  Request,
  Response,
  Validator,
} from "../../protocols/index.js";

export interface UpdateRequest {
  projectName: string;
  fileName: string;
  content: string;
}

export type UpdateResponse = string;
export type RequestValidator = Validator;

export { Controller, NotFoundError, Request, Response, UpdateFileUseCase };
