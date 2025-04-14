import { BaseError } from "./base-error.js";
import { ErrorName } from "./error-names.js";

export class NotFoundError extends BaseError {
  constructor(name: string) {
    super(`Resource not found: ${name}`, ErrorName.NOT_FOUND_ERROR);
  }
}
