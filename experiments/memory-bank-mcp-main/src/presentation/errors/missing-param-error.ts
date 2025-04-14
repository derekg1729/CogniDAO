import { BaseError } from "./base-error.js";
import { ErrorName } from "./error-names.js";

export class MissingParamError extends BaseError {
  constructor(paramName: string) {
    super(`Missing parameter: ${paramName}`, ErrorName.MISSING_PARAM_ERROR);
  }
}
