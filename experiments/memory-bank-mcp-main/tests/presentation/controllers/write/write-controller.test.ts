import { describe, expect, it, vi } from "vitest";
import { WriteRequest } from "../../../../src/presentation/controllers/write/protocols.js";
import { WriteController } from "../../../../src/presentation/controllers/write/write-controller.js";
import { UnexpectedError } from "../../../../src/presentation/errors/index.js";
import { makeValidator, makeWriteFileUseCase } from "../../mocks/index.js";

const makeSut = () => {
  const validatorStub = makeValidator<WriteRequest>();
  const writeFileUseCaseStub = makeWriteFileUseCase();
  const sut = new WriteController(writeFileUseCaseStub, validatorStub);
  return {
    sut,
    validatorStub,
    writeFileUseCaseStub,
  };
};

describe("WriteController", () => {
  it("should call validator with correct values", async () => {
    const { sut, validatorStub } = makeSut();
    const validateSpy = vi.spyOn(validatorStub, "validate");
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    await sut.handle(request);
    expect(validateSpy).toHaveBeenCalledWith(request.body);
  });

  it("should return 400 if validator returns an error", async () => {
    const { sut, validatorStub } = makeSut();
    vi.spyOn(validatorStub, "validate").mockReturnValueOnce(
      new Error("any_error")
    );
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 400,
      body: new Error("any_error"),
    });
  });

  it("should call WriteFileUseCase with correct values", async () => {
    const { sut, writeFileUseCaseStub } = makeSut();
    const writeFileSpy = vi.spyOn(writeFileUseCaseStub, "writeFile");
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    await sut.handle(request);
    expect(writeFileSpy).toHaveBeenCalledWith({
      projectName: "any_project",
      fileName: "any_file",
      content: "any_content",
    });
  });

  it("should return 500 if WriteFileUseCase throws", async () => {
    const { sut, writeFileUseCaseStub } = makeSut();
    vi.spyOn(writeFileUseCaseStub, "writeFile").mockRejectedValueOnce(
      new Error("any_error")
    );
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 500,
      body: new UnexpectedError(new Error("any_error")),
    });
  });

  it("should return 200 if valid data is provided", async () => {
    const { sut } = makeSut();
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 200,
      body: "File any_file written successfully to project any_project",
    });
  });
});
