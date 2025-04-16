import { describe, expect, it } from "vitest";
import { MissingParamError } from "../../src/presentation/errors/index.js";
import { RequiredFieldValidator } from "../../src/validators/required-field-validator.js";

describe("RequiredFieldValidator", () => {
  it("should return MissingParamError if field is not provided", () => {
    const sut = new RequiredFieldValidator("field");
    const input = {};
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(MissingParamError);
    expect(error?.message).toBe("Missing parameter: field");
  });

  it("should return MissingParamError if field is undefined", () => {
    const sut = new RequiredFieldValidator("field");
    const input = { field: undefined };
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(MissingParamError);
    expect(error?.message).toBe("Missing parameter: field");
  });

  it("should return MissingParamError if field is null", () => {
    const sut = new RequiredFieldValidator("field");
    const input = { field: null };
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(MissingParamError);
    expect(error?.message).toBe("Missing parameter: field");
  });

  it("should return MissingParamError if field is empty string", () => {
    const sut = new RequiredFieldValidator("fieldEmpty");
    const input = { fieldEmpty: "" };
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(MissingParamError);
    expect(error?.message).toBe("Missing parameter: fieldEmpty");
  });

  it("should return MissingParamError if input is null", () => {
    const sut = new RequiredFieldValidator("field");
    const error = sut.validate(null);

    expect(error).toBeInstanceOf(MissingParamError);
    expect(error?.message).toBe("Missing parameter: field");
  });

  it("should return MissingParamError if input is undefined", () => {
    const sut = new RequiredFieldValidator("field");
    const error = sut.validate(undefined);

    expect(error).toBeInstanceOf(MissingParamError);
    expect(error?.message).toBe("Missing parameter: field");
  });

  it("should not return error if field is zero", () => {
    const sut = new RequiredFieldValidator("fieldZero");
    const input = { fieldZero: 0 };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should not return error if field is false", () => {
    const sut = new RequiredFieldValidator("fieldFalse");
    const input = { fieldFalse: false };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should not return error if field is provided", () => {
    const sut = new RequiredFieldValidator("field");
    const input = { field: "any_value" };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });
});
