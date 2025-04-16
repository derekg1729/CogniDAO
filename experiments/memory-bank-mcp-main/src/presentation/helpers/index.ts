import { NotFoundError, UnexpectedError } from "../errors/index.js";
import { type Response } from "../protocols/index.js";

export const badRequest = (error: Error): Response => ({
  statusCode: 400,
  body: error,
});

export const notFound = (resourceName: string): Response => ({
  statusCode: 404,
  body: new NotFoundError(resourceName),
});

export const serverError = (error: Error): Response => ({
  statusCode: 500,
  body: new UnexpectedError(error),
});

export const ok = (data: any): Response => ({
  statusCode: 200,
  body: data,
});
