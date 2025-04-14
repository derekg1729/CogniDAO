import { describe, expect, it, vi } from "vitest";
import { ListProjectsController } from "../../../../src/presentation/controllers/list-projects/list-projects-controller.js";
import { UnexpectedError } from "../../../../src/presentation/errors/index.js";
import { makeListProjectsUseCase } from "../../mocks/index.js";

const makeSut = () => {
  const listProjectsUseCaseStub = makeListProjectsUseCase();
  const sut = new ListProjectsController(listProjectsUseCaseStub);
  return {
    sut,
    listProjectsUseCaseStub,
  };
};

describe("ListProjectsController", () => {
  it("should call ListProjectsUseCase", async () => {
    const { sut, listProjectsUseCaseStub } = makeSut();
    const listProjectsSpy = vi.spyOn(listProjectsUseCaseStub, "listProjects");
    await sut.handle();
    expect(listProjectsSpy).toHaveBeenCalled();
  });

  it("should return 500 if ListProjectsUseCase throws", async () => {
    const { sut, listProjectsUseCaseStub } = makeSut();
    vi.spyOn(listProjectsUseCaseStub, "listProjects").mockRejectedValueOnce(
      new Error("any_error")
    );
    const response = await sut.handle();
    expect(response).toEqual({
      statusCode: 500,
      body: new UnexpectedError(new Error("any_error")),
    });
  });

  it("should return 200 with projects on success", async () => {
    const { sut } = makeSut();
    const response = await sut.handle();
    expect(response).toEqual({
      statusCode: 200,
      body: ["project1", "project2"],
    });
  });
});
