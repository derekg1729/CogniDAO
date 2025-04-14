import { Validator } from "../../../../presentation/protocols/validator.js";
import {
  ParamNameValidator,
  RequiredFieldValidator,
  ValidatorComposite,
} from "../../../../validators/index.js";
import { PathSecurityValidator } from "../../../../validators/path-security-validator.js";

const makeValidations = (): Validator[] => {
  return [
    new RequiredFieldValidator("projectName"),
    new RequiredFieldValidator("fileName"),
    new RequiredFieldValidator("content"),
    new ParamNameValidator("projectName"),
    new ParamNameValidator("fileName"),
    new PathSecurityValidator("projectName"),
    new PathSecurityValidator("fileName"),
  ];
};

export const makeWriteValidation = (): Validator => {
  const validations = makeValidations();
  return new ValidatorComposite(validations);
};
