import { ListProjectFilesUseCase } from "../../../domain/usecases/list-project-files.js";
import {
  Controller,
  Request,
  Response,
  Validator,
} from "../../protocols/index.js";

export interface ListProjectFilesRequest {
  projectName: string;
}

export type ListProjectFilesResponse = string[];

export { Controller, ListProjectFilesUseCase, Request, Response, Validator };
